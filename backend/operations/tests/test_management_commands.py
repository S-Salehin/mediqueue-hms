import io
import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import RoleAssignment, StaffMFADevice, User
from communications.models import NotificationPreference
from core.models import AuditEvent
from directory.models import ConsentRecord, Hospital, PatientProfile


class BootstrapAdministratorCommandTests(TestCase):
    def test_bootstrap_creates_only_the_first_admin_with_mfa_and_audit(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"BOOTSTRAP_ADMIN_PASSWORD": "FirstAdminPassword!2026"}):
            call_command(
                "bootstrap_admin",
                email="first.admin@example.test",
                display_name="First Administrator",
                stdout=output,
            )
        user = User.objects.get(email="first.admin@example.test")
        self.assertTrue(
            user.role_assignments.filter(
                role=RoleAssignment.Role.ADMINISTRATOR,
                is_active=True,
            ).exists()
        )
        self.assertTrue(StaffMFADevice.objects.filter(user=user, confirmed_at__isnull=False).exists())
        event = AuditEvent.objects.get(event_type="bootstrap.first_administrator_created")
        self.assertEqual(event.subject_id, user.pk)
        self.assertNotIn("password", str(event.changes).lower())
        self.assertNotIn("secret", str(event.changes).lower())
        with patch.dict(os.environ, {"BOOTSTRAP_ADMIN_PASSWORD": "AnotherAdminPassword!2026"}):
            with self.assertRaises(CommandError):
                call_command(
                    "bootstrap_admin",
                    email="second.admin@example.test",
                    display_name="Second Administrator",
                )
        self.assertEqual(User.objects.count(), 1)


@override_settings(DEBUG=True)
class SyntheticSeedCommandTests(TestCase):
    def test_seed_enforces_pilot_bounds(self):
        for doctors, appointments in ((0, 1), (31, 1), (1, 0), (1, 501)):
            with self.subTest(doctors=doctors, appointments=appointments), self.assertRaises(CommandError):
                call_command("seed_synthetic", doctors=doctors, appointments=appointments, verbosity=0)

    def test_seed_marks_assisted_registration_and_creates_immutable_consents(self):
        call_command("seed_synthetic", doctors=1, appointments=1, stdout=io.StringIO())
        hospital = Hospital.objects.get()
        patients = PatientProfile.objects.order_by("created_at")
        self.assertEqual(patients.count(), 100)
        self.assertFalse(
            patients.exclude(registration_source=PatientProfile.RegistrationSource.RECEPTION).exists()
        )
        self.assertEqual(
            ConsentRecord.objects.filter(
                notice_version=hospital.active_privacy_notice,
                purpose="service_and_privacy_notice",
                decision=True,
                channel=ConsentRecord.Channel.ASSISTED,
                actor__isnull=False,
            ).count(),
            patients.count(),
        )
        claimed = patients.get(is_claimed=True)
        self.assertTrue(
            ConsentRecord.objects.filter(
                patient=claimed,
                purpose="email_notifications",
                decision=True,
                channel=ConsentRecord.Channel.ASSISTED,
            ).exists()
        )
        preference = NotificationPreference.objects.get(user=claimed.user)
        self.assertTrue(preference.appointment_email)
        self.assertTrue(preference.queue_email)
