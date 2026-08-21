import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Notification, NotificationAttempt, NotificationOutbox, NotificationPreference

SAFE_TEMPLATES = {
    "verify_email": ("Verify your hospital account", "Open this secure link to verify your account: {url}"),
    "reset_password": ("Reset your hospital account password", "Open this secure link to reset your password: {url}"),
    "staff_invitation": ("Hospital staff account invitation", "Open this secure link to accept your staff invitation: {url}"),
    "claim_patient": ("Complete your hospital account", "Open this secure link to complete your account: {url}"),
    "appointment_booked": ("Your hospital appointment is confirmed", "Sign in to review your confirmed appointment: {url}"),
    "appointment_changed": ("Your hospital appointment was updated", "Sign in to review the appointment update: {url}"),
    "queue_update": ("Your hospital queue has an update", "Sign in to review your queue status: {url}"),
}

TOKEN_PURPOSES = {
    "verify_email": "verify_email",
    "reset_password": "reset_password",
    "claim_patient": "claim_patient",
}


def secure_link_is_active(job):
    """Reject superseded or expired account links before an email is sent."""
    token = str(job.template_data.get("token", ""))
    if not token:
        return False
    from accounts.models import AccountToken, StaffInvitation
    from accounts.services import digest_token

    now = timezone.now()
    token_digest = digest_token(token)
    if job.template_key == "staff_invitation":
        return StaffInvitation.objects.filter(
            pk=job.related_id,
            token_digest=token_digest,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=now,
        ).exists()
    purpose = TOKEN_PURPOSES.get(job.template_key)
    if not purpose:
        return True
    account_token = AccountToken.objects.filter(
        token_digest=token_digest,
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=now,
    ).first()
    if not account_token:
        return False
    if job.template_key in {"verify_email", "reset_password"}:
        return job.related_id == account_token.user_id
    return True


def enqueue_email(recipient, template_key, template_data, related_id=None):
    if template_key not in SAFE_TEMPLATES:
        raise ValueError("Unknown notification template")
    return NotificationOutbox.objects.create(
        recipient=recipient,
        template_key=template_key,
        template_data=template_data,
        related_id=related_id,
        next_attempt_at=timezone.now(),
    )


def notify_user(user, category, title, body, related_id=None, template_key=None, template_data=None):
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    notification = None
    if preference.in_app:
        notification = Notification.objects.create(user=user, category=category, title=title, body=body, related_id=related_id)
    email_enabled = preference.queue_email if category == "queue" else preference.appointment_email
    if template_key and email_enabled:
        enqueue_email(user.email, template_key, template_data or {}, related_id=related_id)
    return notification


def render_email(job):
    subject, body_template = SAFE_TEMPLATES[job.template_key]
    if "token" in job.template_data:
        route = {
            "verify_email": "verify-email",
            "reset_password": "reset-password",
            "staff_invitation": "accept-invitation",
            "claim_patient": "claim-account",
        }[job.template_key]
        url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/{route}?token={job.template_data['token']}"
    else:
        url = str(job.template_data.get("url", settings.PUBLIC_BASE_URL))
        if url.startswith("/"):
            url = settings.PUBLIC_BASE_URL.rstrip("/") + url
    return subject, body_template.format(url=url)


def process_one_outbox():
    now = timezone.now()
    with transaction.atomic():
        job = (
            NotificationOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                Q(state__in=[NotificationOutbox.State.PENDING, NotificationOutbox.State.FAILED], next_attempt_at__lte=now)
                | Q(state=NotificationOutbox.State.PROCESSING, leased_at__lte=now - timedelta(minutes=10))
            )
            .order_by("created_at")
            .first()
        )
        if not job:
            return False
        if job.attempt_count >= 5:
            job.state = NotificationOutbox.State.DEAD
            job.leased_at = None
            job.template_data = {}
            job.save(update_fields=["state", "leased_at", "template_data", "updated_at"])
            return True
        if job.template_key in {*TOKEN_PURPOSES, "staff_invitation"} and not secure_link_is_active(job):
            job.state = NotificationOutbox.State.DEAD
            job.leased_at = None
            job.template_data = {}
            job.last_error_category = "expired_or_superseded"
            job.save(update_fields=["state", "leased_at", "template_data", "last_error_category", "updated_at"])
            return True
        job.state = NotificationOutbox.State.PROCESSING
        job.leased_at = now
        job.attempt_count += 1
        job.save(update_fields=["state", "leased_at", "attempt_count", "updated_at"])
        job_id = job.pk
    job = NotificationOutbox.objects.get(pk=job_id)
    try:
        subject, body = render_email(job)
        delivered = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [job.recipient], fail_silently=False)
        if delivered != 1:
            raise RuntimeError("email_backend_rejected")
    except Exception as exc:
        category = exc.__class__.__name__.lower()[:60]
        with transaction.atomic():
            job = NotificationOutbox.objects.select_for_update().get(pk=job_id)
            terminal = job.attempt_count >= 5
            job.state = NotificationOutbox.State.DEAD if terminal else NotificationOutbox.State.FAILED
            job.last_error_category = category
            base_seconds = min(3600, (2**job.attempt_count) * 60)
            jitter_seconds = secrets.randbelow(max(1, base_seconds // 4) + 1)
            job.next_attempt_at = timezone.now() + timedelta(seconds=base_seconds + jitter_seconds)
            job.leased_at = None
            if terminal:
                job.template_data = {}
            fields = ["state", "last_error_category", "next_attempt_at", "leased_at", "updated_at"]
            if terminal:
                fields.append("template_data")
            job.save(update_fields=fields)
            NotificationAttempt.objects.create(outbox=job, attempt_number=job.attempt_count, result="failed", safe_error_category=category)
        return True
    with transaction.atomic():
        job = NotificationOutbox.objects.select_for_update().get(pk=job_id)
        job.state = NotificationOutbox.State.SENT
        job.sent_at = timezone.now()
        job.leased_at = None
        job.provider_reference = hashlib.sha256(f"{job.pk}:{job.sent_at.isoformat()}".encode()).hexdigest()[:32]
        job.template_data = {}
        job.save(update_fields=["state", "sent_at", "leased_at", "provider_reference", "template_data", "updated_at"])
        NotificationAttempt.objects.create(outbox=job, attempt_number=job.attempt_count, result="sent", provider_reference=job.provider_reference)
    return True
