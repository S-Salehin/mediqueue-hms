import getpass
import os
import uuid

import pyotp
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import RoleAssignment, StaffMFADevice, User
from accounts.services import generate_recovery_codes
from core.models import AuditEvent


class Command(BaseCommand):
    help = "Create the first application administrator and enroll TOTP MFA."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--display-name", required=True)
        parser.add_argument("--password-env", default="BOOTSTRAP_ADMIN_PASSWORD")

    @transaction.atomic
    def handle(self, *args, **options):
        if (
            User.objects.exists()
            or RoleAssignment.objects.filter(
                role=RoleAssignment.Role.ADMINISTRATOR,
                is_active=True,
            ).exists()
        ):
            raise CommandError("Bootstrap is available only before the first user exists. Use the protected staff invitation workflow.")
        password = os.environ.get(options["password_env"]) or getpass.getpass("Administrator password: ")
        email = User.objects.normalize_email(options["email"])
        candidate = User(email=email, display_name=options["display_name"])
        try:
            validate_password(password, user=candidate)
        except Exception as exc:
            raise CommandError("The password does not pass configured validation.") from exc
        user = User.objects.create_user(
            email,
            password,
            display_name=options["display_name"],
            is_staff=True,
            email_verified_at=timezone.now(),
        )
        RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.ADMINISTRATOR)
        secret = pyotp.random_base32()
        device = StaffMFADevice(user=user, confirmed_at=timezone.now())
        device.set_secret(secret)
        device.save()
        recovery_codes = generate_recovery_codes(device)
        device.save(update_fields=["confirmed_at", "recovery_code_digests", "updated_at"])
        AuditEvent.objects.create(
            event_type="bootstrap.first_administrator_created",
            actor=None,
            actor_role="system",
            subject_type="User",
            subject_id=user.pk,
            action="bootstrap",
            changes={"role": RoleAssignment.Role.ADMINISTRATOR, "mfa_configured": True},
            reason="Initial installation bootstrap",
            request_id=uuid.uuid4(),
        )
        uri = pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name="Hospital Operations")
        self.stdout.write(self.style.SUCCESS(f"Administrator created: {user.email}"))
        self.stdout.write("Enroll this TOTP URI now. It will not be stored in logs by the application:")
        self.stdout.write(uri)
        self.stdout.write("Store these one-time recovery codes securely. They will not be shown again:")
        for recovery_code in recovery_codes:
            self.stdout.write(recovery_code)
