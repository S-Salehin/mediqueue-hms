import uuid
from unittest.mock import patch

import pyotp
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AccountToken, RoleAssignment, StaffInvitation, User
from communications.models import NotificationOutbox
from core.models import AuditEvent
from directory.models import Hospital, PatientProfile, PrivacyNoticeVersion


class RegistrationAndStaffIdentityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hospital = Hospital.objects.create(display_name="Identity Test Hospital", short_name="ITH")
        self.notice = PrivacyNoticeVersion.objects.create(
            hospital=self.hospital, version="identity-1", title="Privacy", content="Synthetic test notice", effective_at=timezone.now(), is_published=True
        )
        self.hospital.active_privacy_notice = self.notice
        self.hospital.save(update_fields=["active_privacy_notice", "updated_at"])

    def registration_payload(self, **changes):
        payload = {
            "email": "newpatient@example.test",
            "password": "VeryStrongPatient!2026",
            "full_name": "New Synthetic Patient",
            "phone": "+8801800000888",
            "date_of_birth": "1994-03-10",
            "sex": "unspecified",
            "address": "Synthetic address",
            "privacy_notice_id": str(self.notice.pk),
            "privacy_accepted": True,
        }
        payload.update(changes)
        return payload

    def test_registration_creates_unverified_patient_consent_and_outbox(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            self.registration_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="newpatient@example.test")
        self.assertIsNone(user.email_verified_at)
        self.assertTrue(user.role_assignments.filter(role="patient", is_active=True).exists())
        self.assertEqual(user.patient_profile.consents.count(), 1)
        self.assertTrue(NotificationOutbox.objects.filter(recipient=user.email, template_key="verify_email").exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="patient.registered", subject_id=user.patient_profile.pk).exists())
        self.assertNotIn("development_verification_token", response.json())

    def test_email_verification_token_is_single_use(self):
        self.test_registration_creates_unverified_patient_consent_and_outbox()
        outbox = NotificationOutbox.objects.get(template_key="verify_email")
        raw = outbox.template_data["token"]
        first = self.client.post("/api/v1/auth/email/verify/", {"token": raw}, format="json")
        second = self.client.post("/api/v1/auth/email/verify/", {"token": raw}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        user = User.objects.get(email="newpatient@example.test")
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(AuditEvent.objects.filter(event_type="authentication.email_verified", subject_id=user.pk).exists())

    def test_email_verification_resend_is_generic_and_supersedes_the_old_link(self):
        self.test_registration_creates_unverified_patient_consent_and_outbox()
        user = User.objects.get(email="newpatient@example.test")
        old_job = NotificationOutbox.objects.get(template_key="verify_email")
        old_token = old_job.template_data["token"]
        known = self.client.post("/api/v1/auth/email/resend/", {"email": user.email}, format="json")
        unknown = self.client.post("/api/v1/auth/email/resend/", {"email": "unknown@example.test"}, format="json")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.json(), unknown.json())
        old_job.refresh_from_db()
        self.assertEqual(old_job.state, NotificationOutbox.State.DEAD)
        self.assertEqual(self.client.post("/api/v1/auth/email/verify/", {"token": old_token}, format="json").status_code, 409)
        self.assertEqual(NotificationOutbox.objects.filter(template_key="verify_email", state=NotificationOutbox.State.PENDING).count(), 1)
        self.assertTrue(AuditEvent.objects.filter(event_type="authentication.email_verification_resent", subject_id=user.pk).exists())

    def test_unknown_registration_fields_are_rejected(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "unknownfield@example.test",
                "password": "VeryStrongPatient!2026",
                "full_name": "Synthetic Patient",
                "phone": "+8801800000777",
                "date_of_birth": "1994-03-10",
                "sex": "unspecified",
                "address": "Synthetic",
                "privacy_notice_id": str(self.notice.pk),
                "privacy_accepted": True,
                "is_staff": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("is_staff", response.json()["field_errors"])
        self.assertFalse(User.objects.filter(email="unknownfield@example.test").exists())

    def test_administrator_invites_staff_with_idempotency_and_totp_enrollment(self):
        admin = User.objects.create_user(
            "identity-admin@example.test", "StrongAdministrator!2026", display_name="Identity Admin", email_verified_at=timezone.now(), is_staff=True
        )
        RoleAssignment.objects.create(user=admin, role=RoleAssignment.Role.ADMINISTRATOR)
        self.client.force_authenticate(user=admin)
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        key = str(uuid.uuid4())
        first = self.client.post(
            "/api/v1/admin/staff-invitations/", {"email": "newdoctor@example.test", "role": "doctor"}, format="json", HTTP_IDEMPOTENCY_KEY=key
        )
        replay = self.client.post(
            "/api/v1/admin/staff-invitations/", {"email": "newdoctor@example.test", "role": "doctor"}, format="json", HTTP_IDEMPOTENCY_KEY=key
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(StaffInvitation.objects.count(), 1)
        raw = NotificationOutbox.objects.get(template_key="staff_invitation").template_data["token"]
        anonymous = APIClient()
        accepted = anonymous.post(
            "/api/v1/auth/staff-invitations/accept/", {"token": raw, "display_name": "New Synthetic Doctor", "password": "StrongNewDoctor!2026"}, format="json"
        )
        self.assertEqual(accepted.status_code, 201)
        secret = accepted.json()["totp_secret"]
        confirmed = anonymous.post("/api/v1/auth/mfa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json")
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.json()["mfa_verified"])
        doctor = User.objects.get(email="newdoctor@example.test")
        self.assertTrue(doctor.role_assignments.filter(role="doctor", is_active=True).exists())
        self.assertTrue(doctor.mfa_devices.filter(confirmed_at__isnull=False).exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="authentication.mfa_enrolled", subject_id=doctor.pk).exists())

    def test_registration_rejects_future_and_implausibly_old_birth_dates(self):
        base = {
            "email": "dob@example.test",
            "password": "VeryStrongPatient!2026",
            "full_name": "DOB Synthetic Patient",
            "phone": "+8801800000666",
            "sex": "unspecified",
            "address": "Synthetic",
            "privacy_notice_id": str(self.notice.pk),
            "privacy_accepted": True,
        }
        future = self.client.post("/api/v1/auth/register/", {**base, "date_of_birth": "2099-01-01"}, format="json")
        old = self.client.post("/api/v1/auth/register/", {**base, "date_of_birth": "1800-01-01"}, format="json")
        self.assertEqual(future.status_code, 400)
        self.assertEqual(old.status_code, 400)
        self.assertIn("date_of_birth", future.json()["field_errors"])
        self.assertFalse(User.objects.filter(email=base["email"]).exists())

    def test_registration_rejects_stale_notice_and_existing_patient_identity(self):
        stale = PrivacyNoticeVersion.objects.create(
            hospital=self.hospital,
            version="identity-old",
            title="Old privacy notice",
            content="Synthetic old notice",
            effective_at=timezone.now(),
            is_published=True,
        )
        stale_response = self.client.post(
            "/api/v1/auth/register/",
            self.registration_payload(privacy_notice_id=str(stale.pk)),
            format="json",
        )
        self.assertEqual(stale_response.status_code, 400)
        self.assertEqual(stale_response.json()["code"], "privacy_notice_invalid")
        PatientProfile.objects.create(
            hospital=self.hospital,
            full_name="Existing Assisted Patient",
            email="existing@example.test",
            phone="+8801800000999",
            date_of_birth=timezone.localdate().replace(year=1990),
            address="Synthetic",
        )
        duplicate = self.client.post(
            "/api/v1/auth/register/",
            self.registration_payload(email="different@example.test", phone="+8801800000999"),
            format="json",
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["code"], "existing_patient_record")
        self.assertNotIn("Existing Assisted Patient", duplicate.content.decode())

    def test_assisted_patient_claim_sets_password_and_is_single_use(self):
        receptionist = User.objects.create_user(
            "claim-reception@example.test",
            "StrongReception!2026",
            display_name="Claim Reception",
            email_verified_at=timezone.now(),
            is_staff=True,
        )
        RoleAssignment.objects.create(user=receptionist, role=RoleAssignment.Role.RECEPTIONIST)
        patient = PatientProfile.objects.create(
            hospital=self.hospital,
            full_name="Claim Synthetic Patient",
            phone="+8801800000555",
            date_of_birth=timezone.localdate().replace(year=1992),
            address="Synthetic",
        )
        self.client.force_authenticate(user=receptionist)
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        invitation = self.client.post(
            f"/api/v1/reception/patients/{patient.pk}/claim-invitations/",
            {"email": "claimed@example.test"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(invitation.status_code, 201)
        raw = NotificationOutbox.objects.get(template_key="claim_patient").template_data["token"]
        anonymous = APIClient()
        accepted = anonymous.post(
            "/api/v1/auth/patient-claims/accept/",
            {"token": raw, "password": "ClaimedPatientStrong!2026"},
            format="json",
        )
        replay = anonymous.post(
            "/api/v1/auth/patient-claims/accept/",
            {"token": raw, "password": "ClaimedPatientStrong!2026"},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(replay.status_code, 409)
        patient.refresh_from_db()
        self.assertTrue(patient.is_claimed)
        self.assertTrue(patient.user.check_password("ClaimedPatientStrong!2026"))
        self.assertIsNotNone(patient.user.email_verified_at)

    def test_claim_failure_rolls_back_single_use_token_and_identity_changes(self):
        user = User.objects.create_user("rollback-claim@example.test", None, display_name="Rollback Claim")
        RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.PATIENT)
        patient = PatientProfile.objects.create(
            hospital=self.hospital,
            user=user,
            full_name="Rollback Claim",
            email=user.email,
            phone="+8801800000444",
            date_of_birth=timezone.localdate().replace(year=1991),
            address="Synthetic",
        )
        from accounts.services import issue_account_token

        raw = issue_account_token(user, AccountToken.Purpose.CLAIM_PATIENT, minutes=60)
        client = APIClient()
        with patch("accounts.views.audit", side_effect=RuntimeError("synthetic rollback")):
            response = client.post(
                "/api/v1/auth/patient-claims/accept/",
                {"token": raw, "password": "RollbackPatientStrong!2026"},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        token = AccountToken.objects.get(user=user, purpose=AccountToken.Purpose.CLAIM_PATIENT)
        self.assertIsNone(token.used_at)
        user.refresh_from_db()
        patient.refresh_from_db()
        self.assertFalse(user.has_usable_password())
        self.assertFalse(patient.is_claimed)
