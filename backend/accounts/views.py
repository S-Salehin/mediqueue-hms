import pyotp
from django.conf import settings
from django.contrib.auth import authenticate, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import BoundedPagination
from core.permissions import IsAdministrator, IsOperationalStaff, active_roles
from core.services import audit, idempotent
from core.throttling import DatabaseScopedRateThrottle

from .models import AccountToken, LoginAudit, RoleAssignment, StaffMFADevice, User
from .serializers import (
    ClaimPatientAcceptSerializer,
    ForgotPasswordSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    LoginSerializer,
    MFAReplacementStartSerializer,
    MFAVerifySerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    TokenSerializer,
)
from .services import (
    accept_invitation,
    clear_authentication_failures,
    confirm_enrollment_totp,
    confirm_mfa_replacement,
    consume_account_token,
    create_staff_invitation,
    establish_session,
    issue_account_token,
    login_audit,
    record_authentication_failure,
    start_mfa_replacement,
    verify_mfa_code,
)


@method_decorator(csrf_protect, name="dispatch")
class PublicWriteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"


def session_payload(request):
    if not request.user.is_authenticated:
        return {"authenticated": False, "user": None, "roles": [], "mfa_verified": False, "permissions": []}
    roles = sorted(active_roles(request.user))
    permissions = []
    mapping = {
        "patient": ["appointments.self", "profile.self", "queue.self", "notifications.self"],
        "doctor": ["schedule.assigned", "queue.assigned.operate"],
        "receptionist": ["patients.search", "appointments.manage", "queue.operate", "payments.record"],
        "administrator": ["configuration.manage", "staff.invite", "audit.read"],
    }
    for role in roles:
        permissions.extend(mapping.get(role, []))
    return {
        "authenticated": True,
        "user": {"id": str(request.user.pk), "email": request.user.email, "display_name": request.user.display_name},
        "roles": roles,
        "mfa_verified": bool(request.session.get("mfa_verified", False)),
        "permissions": sorted(set(permissions)),
    }


class CSRFView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class SessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(session_payload(request))


class LoginView(PublicWriteView):
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_email(serializer.validated_data["email"])
        candidate = User.objects.filter(email=email).first()
        if candidate and candidate.locked_until and candidate.locked_until > timezone.now():
            login_audit(request, LoginAudit.Result.FAILED, user=candidate)
            return Response(
                {
                    "status": 429,
                    "code": "account_temporarily_locked",
                    "title": "Sign in temporarily unavailable",
                    "detail": "Too many sign in attempts. Wait before trying again.",
                    "field_errors": {},
                    "request_id": str(request.request_id),
                },
                status=429,
            )
        user = authenticate(request, username=email, password=serializer.validated_data["password"])
        if not user or not user.is_active or not user.email_verified_at:
            if candidate:
                with transaction.atomic():
                    record_authentication_failure(candidate)
                    login_audit(request, LoginAudit.Result.FAILED, user=candidate, email=email)
            else:
                login_audit(request, LoginAudit.Result.FAILED, email=email)
            return Response(
                {
                    "status": 401,
                    "code": "invalid_credentials",
                    "title": "Sign in failed",
                    "detail": "The email or password is incorrect.",
                    "field_errors": {},
                    "request_id": str(request.request_id),
                },
                status=401,
            )
        roles = active_roles(user)
        if roles - {RoleAssignment.Role.PATIENT}:
            if not user.mfa_devices.filter(confirmed_at__isnull=False, revoked_at__isnull=True).exists():
                login_audit(request, LoginAudit.Result.FAILED, user=user)
                return Response({"detail": "Staff MFA enrollment is required.", "code": "mfa_enrollment_required"}, status=403)
            request.session.flush()
            request.session["pending_mfa_user_id"] = str(user.pk)
            request.session["mfa_challenge_started_at"] = int(timezone.now().timestamp())
            request.session.set_expiry(settings.MFA_CHALLENGE_TIMEOUT_SECONDS)
            login_audit(request, LoginAudit.Result.MFA_REQUIRED, user=user)
            return Response({"mfa_required": True})
        establish_session(request, user)
        clear_authentication_failures(user)
        login_audit(request, LoginAudit.Result.SUCCESS, user=user)
        return Response(session_payload(request))


class MFAVerifyView(PublicWriteView):
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = request.session.get("pending_mfa_user_id")
        user = User.objects.filter(pk=user_id, is_active=True).first() if user_id else None
        if user and user.locked_until and user.locked_until > timezone.now():
            login_audit(request, LoginAudit.Result.MFA_FAILED, user=user)
            return Response(
                {"detail": "Too many sign in attempts. Wait before trying again.", "code": "account_temporarily_locked"},
                status=429,
            )
        device = user.mfa_devices.filter(confirmed_at__isnull=False, revoked_at__isnull=True).first() if user else None
        accepted, used_recovery = verify_mfa_code(device, serializer.validated_data["code"]) if device else (False, False)
        if not accepted:
            with transaction.atomic():
                if user:
                    record_authentication_failure(user)
                login_audit(request, LoginAudit.Result.MFA_FAILED, user=user)
            return Response({"detail": "The authentication code is invalid.", "code": "mfa_invalid"}, status=401)
        request.session.pop("pending_mfa_user_id", None)
        establish_session(request, user, mfa_verified=True)
        clear_authentication_failures(user)
        if used_recovery:
            device.refresh_from_db(fields=["recovery_code_digests"])
            audit(
                request,
                "authentication.recovery_code_used",
                user,
                "mfa_verify",
                {"remaining_codes": len(device.recovery_code_digests)},
            )
        login_audit(request, LoginAudit.Result.SUCCESS, user=user)
        return Response(session_payload(request))


class MFAConfirmView(PublicWriteView):
    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = request.session.get("mfa_enrollment_user_id")
        user = User.objects.filter(pk=user_id, is_active=True).first() if user_id else None
        if user and user.locked_until and user.locked_until > timezone.now():
            return Response(
                {"detail": "Too many sign in attempts. Wait before trying again.", "code": "account_temporarily_locked"},
                status=429,
            )
        device_id = request.session.get("mfa_enrollment_device_id")
        device = (
            user.mfa_devices.filter(
                pk=device_id,
                confirmed_at__isnull=True,
                revoked_at__isnull=True,
            ).first()
            if user and device_id
            else None
        )
        if not device or not confirm_enrollment_totp(device, serializer.validated_data["code"]):
            if user:
                record_authentication_failure(user)
                audit(request, "authentication.mfa_enrollment_failed", user, "mfa_enroll", {})
            return Response({"detail": "The authentication code is invalid.", "code": "mfa_invalid"}, status=400)
        request.session.pop("mfa_enrollment_user_id", None)
        request.session.pop("mfa_enrollment_device_id", None)
        request.session.pop("mfa_enrollment_started_at", None)
        establish_session(request, user, mfa_verified=True)
        clear_authentication_failures(user)
        audit(request, "authentication.mfa_enrolled", user, "mfa_enroll", {})
        return Response(session_payload(request))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        audit(request, "authentication.logout", request.user, "logout")
        logout(request)
        return Response(status=204)


class MFAReplacementStartView(APIView):
    permission_classes = [IsOperationalStaff]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = MFAReplacementStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.get(pk=request.user.pk)
        if user.locked_until and user.locked_until > timezone.now():
            return Response(
                {"detail": "Too many authentication attempts. Wait before trying again.", "code": "account_temporarily_locked"},
                status=429,
            )
        if not user.check_password(serializer.validated_data["current_password"]):
            record_authentication_failure(user)
            return Response(
                {"detail": "The current password is incorrect.", "code": "invalid_current_password"},
                status=400,
            )
        device, secret, recovery_codes = start_mfa_replacement(request)
        request.session["mfa_replacement_device_id"] = str(device.pk)
        request.session["mfa_replacement_started_at"] = int(timezone.now().timestamp())
        return Response(
            {
                "provisioning_uri": pyotp.TOTP(secret).provisioning_uri(
                    user.email,
                    issuer_name="Hospital Operations",
                ),
                "totp_secret": secret,
                "recovery_codes": recovery_codes,
            },
            status=201,
        )


class MFAReplacementConfirmView(APIView):
    permission_classes = [IsOperationalStaff]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = request.session.get("mfa_replacement_device_id")
        device = StaffMFADevice.objects.filter(pk=device_id, user=request.user).first() if device_id else None
        if not device or not confirm_mfa_replacement(request, device, serializer.validated_data["code"]):
            record_authentication_failure(request.user)
            return Response({"detail": "The authentication code is invalid.", "code": "mfa_invalid"}, status=400)
        request.session.pop("mfa_replacement_device_id", None)
        request.session.pop("mfa_replacement_started_at", None)
        clear_authentication_failures(request.user)
        return Response({"replaced": True})


class RegisterView(PublicWriteView):
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from directory.models import ConsentRecord, Hospital, PatientProfile, PrivacyNoticeVersion

        hospital = Hospital.objects.select_for_update().filter(is_active=True, active_privacy_notice_id=serializer.validated_data["privacy_notice_id"]).first()
        notice = (
            PrivacyNoticeVersion.objects.filter(
                pk=serializer.validated_data["privacy_notice_id"],
                hospital=hospital,
                is_published=True,
            ).first()
            if hospital
            else None
        )
        if not notice:
            return Response({"detail": "The selected privacy notice is not available.", "code": "privacy_notice_invalid"}, status=400)
        user = User.objects.create_user(
            serializer.validated_data["email"], serializer.validated_data["password"], display_name=serializer.validated_data["full_name"]
        )
        RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.PATIENT)
        patient = PatientProfile.objects.create(
            hospital=notice.hospital,
            user=user,
            full_name=serializer.validated_data["full_name"],
            phone=serializer.validated_data["phone"],
            date_of_birth=serializer.validated_data["date_of_birth"],
            sex=serializer.validated_data["sex"],
            address=serializer.validated_data["address"],
            email=user.email,
            is_claimed=True,
            registration_source=PatientProfile.RegistrationSource.SELF_SERVICE,
        )
        ConsentRecord.objects.create(
            patient=patient,
            notice_version=notice,
            purpose="service_and_privacy_notice",
            decision=True,
            channel="self_service",
            request_id=request.request_id,
        )
        raw = issue_account_token(user, AccountToken.Purpose.VERIFY_EMAIL, minutes=60)
        from communications.services import enqueue_email

        enqueue_email(user.email, "verify_email", {"token": raw}, related_id=user.pk)
        audit(
            request,
            "patient.registered",
            patient,
            "register",
            {"registration_source": patient.registration_source, "verification_required": True},
        )
        body = {"registered": True, "verification_required": True}
        if settings.DEBUG:
            body["development_verification_token"] = raw
        return Response(body, status=201)


class EmailVerifyView(PublicWriteView):
    @transaction.atomic
    def post(self, request):
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = consume_account_token(serializer.validated_data["token"], AccountToken.Purpose.VERIFY_EMAIL)
        if not user.email_verified_at:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at", "updated_at"])
        if hasattr(user, "patient_profile") and not user.patient_profile.is_claimed:
            user.patient_profile.is_claimed = True
            user.patient_profile.save(update_fields=["is_claimed", "updated_at"])
        audit(request, "authentication.email_verified", user, "verify_email", {})
        return Response({"verified": True})


class EmailVerificationResendView(PublicWriteView):
    @transaction.atomic
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_email(serializer.validated_data["email"])
        user = User.objects.select_for_update().filter(
            email=email,
            is_active=True,
            email_verified_at__isnull=True,
        ).first()
        if user:
            from communications.models import NotificationOutbox

            NotificationOutbox.objects.filter(
                related_id=user.pk,
                template_key="verify_email",
                state__in=[NotificationOutbox.State.PENDING, NotificationOutbox.State.FAILED],
            ).update(
                state=NotificationOutbox.State.DEAD,
                template_data={"invalidated": True},
                last_error_category="superseded",
            )
            raw = issue_account_token(user, AccountToken.Purpose.VERIFY_EMAIL, minutes=60)
            from communications.services import enqueue_email

            enqueue_email(user.email, "verify_email", {"token": raw}, related_id=user.pk)
            audit(request, "authentication.email_verification_resent", user, "verify_email", {})
        return Response({"accepted": True})


class ForgotPasswordView(PublicWriteView):
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "auth"

    @transaction.atomic
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=User.objects.normalize_email(serializer.validated_data["email"]), is_active=True).first()
        if user:
            from communications.models import NotificationOutbox

            NotificationOutbox.objects.filter(
                related_id=user.pk,
                template_key="reset_password",
                state__in=[NotificationOutbox.State.PENDING, NotificationOutbox.State.FAILED],
            ).update(
                state=NotificationOutbox.State.DEAD,
                template_data={"invalidated": True},
                last_error_category="superseded",
            )
            raw = issue_account_token(user, AccountToken.Purpose.RESET_PASSWORD, minutes=30)
            from communications.services import enqueue_email

            enqueue_email(user.email, "reset_password", {"token": raw}, related_id=user.pk)
        return Response({"accepted": True})


class ResetPasswordView(PublicWriteView):
    @transaction.atomic
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = consume_account_token(serializer.validated_data["token"], AccountToken.Purpose.RESET_PASSWORD)
        try:
            validate_password(serializer.validated_data["password"], user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": exc.messages}) from exc
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password", "updated_at"])
        audit(request, "authentication.password_reset", user, "reset_password", {})
        return Response({"reset": True})


class ClaimPatientAcceptView(PublicWriteView):
    @transaction.atomic
    def post(self, request):
        serializer = ClaimPatientAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = consume_account_token(serializer.validated_data["token"], AccountToken.Purpose.CLAIM_PATIENT)
        profile = user.patient_profile
        try:
            validate_password(serializer.validated_data["password"], user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": exc.messages}) from exc
        user.set_password(serializer.validated_data["password"])
        user.email_verified_at = timezone.now()
        user.save(update_fields=["password", "email_verified_at", "updated_at"])
        profile.is_claimed = True
        profile.save(update_fields=["is_claimed", "updated_at"])
        audit(request, "patient.claim_accepted", profile, "claim", {})
        return Response({"claimed": True, "email_verified": True})


class StaffInvitationView(APIView):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            invitation, raw = create_staff_invitation(request, **serializer.validated_data)
            from communications.services import enqueue_email

            enqueue_email(invitation.email, "staff_invitation", {"token": raw}, related_id=invitation.pk)
            body = {"id": str(invitation.pk), "email": invitation.email, "role": invitation.intended_role, "expires_at": invitation.expires_at}
            if settings.DEBUG:
                body["development_invitation_token"] = raw
            return body, 201

        return idempotent(request, "staff.invitation.create", operation)


class StaffListView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        users = (
            User.objects.filter(
                role_assignments__role__in=[RoleAssignment.Role.DOCTOR, RoleAssignment.Role.RECEPTIONIST, RoleAssignment.Role.ADMINISTRATOR],
                role_assignments__is_active=True,
            )
            .distinct()
            .select_related("doctor_profile")
            .prefetch_related("role_assignments", "mfa_devices")
        )
        users = users.order_by("display_name", "email", "id")
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "id": str(user.pk),
                    "email": user.email,
                    "display_name": user.display_name,
                    "roles": sorted(role.role for role in user.role_assignments.all() if role.is_active),
                    "mfa_enabled": any(device.is_confirmed for device in user.mfa_devices.all()),
                    "last_login": user.last_login,
                    "is_active": user.is_active,
                    "doctor_profile_id": str(user.doctor_profile.pk) if hasattr(user, "doctor_profile") else None,
                }
                for user in page
            ]
        )


class StaffDeactivateView(APIView):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, user_id):
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"detail": "A concise operational reason is required.", "code": "reason_required"}, status=400)
        if request.user.pk == user_id:
            return Response({"detail": "Administrators cannot deactivate their own account.", "code": "self_deactivation_forbidden"}, status=409)

        def operation():
            staff_roles = [
                RoleAssignment.Role.DOCTOR,
                RoleAssignment.Role.RECEPTIONIST,
                RoleAssignment.Role.ADMINISTRATOR,
            ]
            user = User.objects.select_for_update().filter(pk=user_id, role_assignments__role__in=staff_roles).first()
            if not user:
                return {"detail": "Staff account not found.", "code": "not_found"}, 404
            before_roles = sorted(user.role_assignments.filter(is_active=True).values_list("role", flat=True))
            before_user_active = user.is_active
            doctor_profile = getattr(user, "doctor_profile", None)
            if doctor_profile and doctor_profile.is_active:
                from operations.models import Appointment, QueueTicket, Schedule

                dependencies = {
                    "confirmed_appointments": Appointment.objects.filter(
                        doctor=doctor_profile,
                        status=Appointment.Status.CONFIRMED,
                    ).count(),
                    "active_schedules": Schedule.objects.filter(
                        doctor=doctor_profile,
                        is_active=True,
                    ).count(),
                    "active_queue_tickets": QueueTicket.objects.filter(
                        appointment__doctor=doctor_profile,
                        state__in=[
                            QueueTicket.State.WAITING,
                            QueueTicket.State.CALLED,
                            QueueTicket.State.IN_SERVICE,
                            QueueTicket.State.DEFERRED,
                        ],
                    ).count(),
                }
                if any(dependencies.values()):
                    return {
                        "detail": "Resolve the doctor's schedules, appointments, and active queue work first.",
                        "code": "active_dependencies",
                        "dependencies": dependencies,
                    }, 409
                doctor_profile.is_active = False
                doctor_profile.save(update_fields=["is_active", "updated_at"])
            disabled_roles = list(user.role_assignments.filter(role__in=staff_roles, is_active=True).values_list("role", flat=True))
            user.role_assignments.filter(role__in=staff_roles, is_active=True).update(is_active=False)
            user.mfa_devices.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
            user.is_active = user.role_assignments.filter(is_active=True).exists()
            user.save(update_fields=["is_active", "updated_at"])
            audit(
                request,
                "staff.deactivated",
                user,
                "deactivate",
                {
                    "before": {"active_roles": before_roles, "user_active": before_user_active},
                    "after": {
                        "active_roles": sorted(user.role_assignments.filter(is_active=True).values_list("role", flat=True)),
                        "user_active": user.is_active,
                    },
                    "disabled_roles": sorted(disabled_roles),
                },
                reason,
            )
            return {"id": str(user.pk), "email": user.email, "is_active": user.is_active, "disabled_roles": sorted(disabled_roles)}, 200

        return idempotent(request, f"staff.{user_id}.deactivate", operation)


class StaffInvitationAcceptView(PublicWriteView):
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, device, secret, recovery_codes, enrollment_resumed = accept_invitation(
            request,
            serializer.validated_data["token"],
            serializer.validated_data["display_name"],
            serializer.validated_data["password"],
        )
        return Response(
            {
                "user_id": str(user.pk),
                "mfa_enrollment_required": True,
                "totp_secret": secret,
                "provisioning_uri": pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name="Hospital Operations"),
                "recovery_codes": recovery_codes,
                "enrollment_resumed": enrollment_resumed,
            },
            status=201,
        )
