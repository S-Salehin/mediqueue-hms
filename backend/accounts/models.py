import hashlib
import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.models import AppendOnlyModel, TimeStampedUUIDModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def normalize_email(self, email):
        return super().normalize_email(email).strip().lower()

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified_at", timezone.now())
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have staff and superuser status.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=160)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    def save(self, *args, **kwargs):
        self.email = User.objects.normalize_email(self.email)
        self.display_name = " ".join((self.display_name or "").split())
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class RoleAssignment(TimeStampedUUIDModel):
    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"
        RECEPTIONIST = "receptionist", "Receptionist"
        ADMINISTRATOR = "administrator", "Administrator"

    user = models.ForeignKey(User, related_name="role_assignments", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    granted_by = models.ForeignKey(User, null=True, blank=True, related_name="granted_roles", on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="unique_user_role")]


class StaffInvitation(TimeStampedUUIDModel):
    email = models.EmailField()
    intended_role = models.CharField(
        max_length=20,
        choices=[choice for choice in RoleAssignment.Role.choices if choice[0] != RoleAssignment.Role.PATIENT],
    )
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    inviter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="staff_invitations")
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["email", "expires_at"])]


def _cipher():
    import base64

    key = hashlib.sha256((settings.MFA_ENCRYPTION_KEY or settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class StaffMFADevice(TimeStampedUUIDModel):
    user = models.ForeignKey(User, related_name="mfa_devices", on_delete=models.CASCADE)
    name = models.CharField(max_length=80, default="Authenticator")
    encrypted_secret = models.BinaryField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    recovery_code_digests = models.JSONField(default=list, blank=True)
    last_used_counter = models.BigIntegerField(default=-1)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def set_secret(self, secret):
        self.encrypted_secret = _cipher().encrypt(secret.encode())

    def get_secret(self):
        return _cipher().decrypt(bytes(self.encrypted_secret)).decode()

    @property
    def is_confirmed(self):
        return bool(self.confirmed_at and not self.revoked_at)


class LoginAudit(AppendOnlyModel):
    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        MFA_REQUIRED = "mfa_required", "MFA required"
        MFA_FAILED = "mfa_failed", "MFA failed"

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    email_digest = models.CharField(max_length=64, blank=True)
    result = models.CharField(max_length=24, choices=Result.choices)
    request_id = models.UUIDField(db_index=True)
    network_context = models.CharField(max_length=80, blank=True)
    client_context = models.CharField(max_length=200, blank=True)


class AccountToken(TimeStampedUUIDModel):
    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        RESET_PASSWORD = "reset_password", "Reset password"
        CLAIM_PATIENT = "claim_patient", "Claim patient"

    user = models.ForeignKey(User, related_name="account_tokens", on_delete=models.CASCADE)
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "expires_at"])]
