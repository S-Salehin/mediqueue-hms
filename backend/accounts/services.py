import hashlib
import re
import secrets
from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth import login
from django.db import transaction
from django.utils import timezone

from core.exceptions import AccountTemporarilyLocked, Conflict
from core.services import audit

from .models import AccountToken, LoginAudit, RoleAssignment, StaffInvitation, StaffMFADevice, User

AUTH_FAILURE_LIMIT = 5
AUTH_LOCK_MINUTES = 15


def digest_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_account_token(user, purpose, minutes=30):
    with transaction.atomic():
        now = timezone.now()
        User.objects.select_for_update().get(pk=user.pk)
        AccountToken.objects.filter(
            user=user,
            purpose=purpose,
            used_at__isnull=True,
        ).update(used_at=now)
        raw = secrets.token_urlsafe(32)
        AccountToken.objects.create(
            user=user,
            purpose=purpose,
            token_digest=digest_token(raw),
            expires_at=now + timedelta(minutes=minutes),
        )
    return raw


def consume_account_token(raw, purpose):
    with transaction.atomic():
        token = AccountToken.objects.select_for_update().filter(token_digest=digest_token(raw), purpose=purpose).first()
        if not token or token.used_at or token.expires_at <= timezone.now():
            raise Conflict("The link is invalid, expired, or has already been used.", code="token_invalid")
        token.used_at = timezone.now()
        token.save(update_fields=["used_at", "updated_at"])
        AccountToken.objects.filter(
            user=token.user,
            purpose=purpose,
            used_at__isnull=True,
        ).exclude(pk=token.pk).update(used_at=token.used_at)
        return token.user


def login_audit(request, result, user=None, email=""):
    ip = request.META.get("REMOTE_ADDR", "")[:80]
    client = request.headers.get("User-Agent", "")[:200]
    LoginAudit.objects.create(
        user=user,
        email_digest=digest_token(email.strip().lower()) if email else "",
        result=result,
        request_id=request.request_id,
        network_context=ip,
        client_context=client,
    )


def _normalized_recovery_code(code):
    return re.sub(r"[\s-]", "", code).upper()


def generate_recovery_codes(device, count=10):
    """Replace recovery codes and return each high-entropy raw code once."""
    raw_codes = []
    digests = []
    for _ in range(count):
        compact = secrets.token_hex(10).upper()
        raw = "-".join(compact[index : index + 5] for index in range(0, len(compact), 5))
        raw_codes.append(raw)
        digests.append(digest_token(compact))
    device.recovery_code_digests = digests
    return raw_codes


def _accepted_totp_counter(secret, code, last_used_counter=-1):
    if not re.fullmatch(r"\d{6}", code):
        return None
    totp = pyotp.TOTP(secret)
    counter = int(timezone.now().timestamp()) // totp.interval
    for offset in (-1, 0, 1):
        candidate = counter + offset
        if candidate > last_used_counter and secrets.compare_digest(
            totp.at(candidate * totp.interval), code
        ):
            return candidate
    return None


@transaction.atomic
def verify_mfa_code(device, code):
    """Verify a non-replayable TOTP or consume one recovery code."""
    locked = StaffMFADevice.objects.select_for_update().get(pk=device.pk)
    if locked.revoked_at or not locked.confirmed_at:
        return False, False
    if re.fullmatch(r"\d{6}", code):
        candidate = _accepted_totp_counter(
            locked.get_secret(), code, locked.last_used_counter
        )
        if candidate is not None:
            locked.last_used_counter = candidate
            locked.save(update_fields=["last_used_counter", "updated_at"])
            return True, False
        return False, False
    normalized = _normalized_recovery_code(code)
    if not re.fullmatch(r"[0-9A-F]{20}", normalized):
        return False, False
    supplied_digest = digest_token(normalized)
    for stored_digest in locked.recovery_code_digests:
        if secrets.compare_digest(stored_digest, supplied_digest):
            remaining = [item for item in locked.recovery_code_digests if item != stored_digest]
            locked.recovery_code_digests = remaining
            locked.save(update_fields=["recovery_code_digests", "updated_at"])
            return True, True
    return False, False


def verify_totp(device, code):
    if not re.fullmatch(r"\d{6}", code):
        return False
    accepted, _ = verify_mfa_code(device, code)
    return accepted


@transaction.atomic
def confirm_enrollment_totp(device, code):
    if not re.fullmatch(r"\d{6}", code):
        return False
    locked = StaffMFADevice.objects.select_for_update().get(pk=device.pk)
    if locked.revoked_at or locked.confirmed_at:
        return False
    counter = _accepted_totp_counter(locked.get_secret(), code, locked.last_used_counter)
    if counter is None:
        return False
    locked.confirmed_at = timezone.now()
    locked.last_used_counter = counter
    locked.save(update_fields=["confirmed_at", "last_used_counter", "updated_at"])
    return True


@transaction.atomic
def record_authentication_failure(user):
    if not user:
        return None
    locked = User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()
    locked.failed_login_count = min(65535, locked.failed_login_count + 1)
    if locked.failed_login_count >= AUTH_FAILURE_LIMIT:
        candidate_lock = now + timedelta(minutes=AUTH_LOCK_MINUTES)
        if not locked.locked_until or locked.locked_until < candidate_lock:
            locked.locked_until = candidate_lock
    locked.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
    return locked


@transaction.atomic
def clear_authentication_failures(user):
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.failed_login_count or locked.locked_until:
        locked.failed_login_count = 0
        locked.locked_until = None
        locked.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
    return locked


@transaction.atomic
def create_staff_invitation(request, email, role, display_name=""):
    email = User.objects.normalize_email(email)
    if User.objects.select_for_update().filter(email=email).exists():
        raise Conflict("An account already uses this email.", code="email_in_use")
    superseded = list(
        StaffInvitation.objects.select_for_update().filter(
            email=email,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
    )
    if superseded:
        now = timezone.now()
        StaffInvitation.objects.filter(pk__in=[item.pk for item in superseded]).update(revoked_at=now)
        from communications.models import NotificationOutbox

        NotificationOutbox.objects.filter(
            related_id__in=[item.pk for item in superseded],
            template_key="staff_invitation",
            state__in=[NotificationOutbox.State.PENDING, NotificationOutbox.State.FAILED],
        ).update(
            state=NotificationOutbox.State.DEAD,
            template_data={"invalidated": True},
            last_error_category="superseded",
        )
    raw = secrets.token_urlsafe(32)
    invitation = StaffInvitation.objects.create(
        email=email,
        intended_role=role,
        token_digest=digest_token(raw),
        expires_at=timezone.now() + timedelta(hours=48),
        inviter=request.user,
    )
    audit(
        request,
        "staff.invitation_created",
        invitation,
        "create",
        {"role": role, "display_name_provided": bool(display_name), "superseded_count": len(superseded)},
    )
    return invitation, raw


def accept_invitation(request, raw_token, display_name, password):
    wrong_password_user = None
    result = None
    with transaction.atomic():
        invitation = StaffInvitation.objects.select_for_update().filter(token_digest=digest_token(raw_token)).first()
        if not invitation or invitation.revoked_at or invitation.expires_at <= timezone.now():
            raise Conflict("The invitation is invalid, expired, or already used.", code="invitation_invalid")
        if invitation.accepted_at:
            user = User.objects.select_for_update().filter(email=invitation.email, is_active=True).first()
            device = user.mfa_devices.select_for_update().filter(confirmed_at__isnull=True, revoked_at__isnull=True).first() if user else None
            if (
                not user
                or not device
                or user.mfa_devices.filter(
                    confirmed_at__isnull=False,
                    revoked_at__isnull=True,
                ).exists()
            ):
                raise Conflict("The invitation is invalid, expired, or already used.", code="invitation_invalid")
            if user.locked_until and user.locked_until > timezone.now():
                raise AccountTemporarilyLocked()
            if not user.check_password(password):
                wrong_password_user = user
            else:
                recovery_codes = generate_recovery_codes(device)
                device.save(update_fields=["recovery_code_digests", "updated_at"])
                secret = device.get_secret()
                request.session["mfa_enrollment_user_id"] = str(user.pk)
                request.session["mfa_enrollment_device_id"] = str(device.pk)
                request.session["mfa_enrollment_started_at"] = int(timezone.now().timestamp())
                request.session.set_expiry(settings.MFA_CHALLENGE_TIMEOUT_SECONDS)
                audit(request, "authentication.mfa_enrollment_resumed", user, "mfa_enroll", {})
                result = (user, device, secret, recovery_codes, True)
        else:
            if User.objects.filter(email=invitation.email).exists():
                raise Conflict("An account already uses this email.", code="email_in_use")
            user = User.objects.create_user(
                invitation.email,
                password,
                display_name=display_name,
                email_verified_at=timezone.now(),
                is_staff=True,
            )
            RoleAssignment.objects.create(user=user, role=invitation.intended_role, granted_by=invitation.inviter)
            secret = pyotp.random_base32()
            device = StaffMFADevice(user=user)
            device.set_secret(secret)
            recovery_codes = generate_recovery_codes(device)
            device.save()
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at", "updated_at"])
            request.session["mfa_enrollment_user_id"] = str(user.pk)
            request.session["mfa_enrollment_device_id"] = str(device.pk)
            request.session["mfa_enrollment_started_at"] = int(timezone.now().timestamp())
            request.session.set_expiry(settings.MFA_CHALLENGE_TIMEOUT_SECONDS)
            audit(
                request,
                "staff.invitation_accepted",
                user,
                "accept_invitation",
                {
                    "before": {"active_roles": []},
                    "after": {"active_roles": [invitation.intended_role]},
                },
            )
            result = (user, device, secret, recovery_codes, False)
    if wrong_password_user:
        record_authentication_failure(wrong_password_user)
        raise Conflict("The invitation or credentials are invalid.", code="invitation_invalid")
    return result


@transaction.atomic
def start_mfa_replacement(request):
    user = User.objects.select_for_update().get(pk=request.user.pk)
    user.mfa_devices.select_for_update().filter(
        confirmed_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    secret = pyotp.random_base32()
    device = StaffMFADevice(user=user, name="Replacement authenticator")
    device.set_secret(secret)
    recovery_codes = generate_recovery_codes(device)
    device.save()
    audit(request, "authentication.mfa_replacement_started", user, "mfa_replace", {})
    return device, secret, recovery_codes


@transaction.atomic
def confirm_mfa_replacement(request, device, code):
    locked = (
        StaffMFADevice.objects.select_for_update()
        .filter(
            pk=device.pk,
            user=request.user,
            confirmed_at__isnull=True,
            revoked_at__isnull=True,
        )
        .first()
    )
    if not locked:
        return False
    counter = _accepted_totp_counter(locked.get_secret(), code, locked.last_used_counter)
    if counter is None:
        return False
    now = timezone.now()
    StaffMFADevice.objects.select_for_update().filter(
        user=request.user,
        confirmed_at__isnull=False,
        revoked_at__isnull=True,
    ).exclude(pk=locked.pk).update(revoked_at=now)
    locked.confirmed_at = now
    locked.last_used_counter = counter
    locked.save(update_fields=["confirmed_at", "last_used_counter", "updated_at"])
    audit(request, "authentication.mfa_replacement_confirmed", request.user, "mfa_replace", {})
    return True


def establish_session(request, user, mfa_verified=False):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.pop("mfa_challenge_started_at", None)
    request.session.pop("mfa_enrollment_started_at", None)
    request.session["mfa_verified"] = bool(mfa_verified)
    now = int(timezone.now().timestamp())
    request.session["session_created_at"] = now
    request.session["session_last_activity_at"] = now
    request.session.set_expiry(settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS)
    request.session.cycle_key()
