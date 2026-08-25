import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import RoleAssignment, StaffMFADevice
from communications.models import Notification, NotificationOutbox, NotificationPreference
from communications.services import enqueue_email
from core.models import AuditEvent, IdempotencyRecord
from directory.models import ConsentRecord, DoctorProfile, PatientProfile, PrivacyNoticeVersion
from operations.models import Appointment, QueueEstimateRecord, QueueTicket
from operations.services import book_appointment, call_next, check_in, transition_ticket

from .base import HospitalTestCase


class APIContractTests(HospitalTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user=user)
        if user.role_assignments.filter(role__in=["doctor", "receptionist", "administrator"], is_active=True).exists():
            session = self.client.session
            session["mfa_verified"] = True
            session.save()

    def idempotency(self):
        return {"HTTP_IDEMPOTENCY_KEY": str(uuid.uuid4())}

    def test_public_directory_and_health_are_anonymous(self):
        hospital = self.client.get("/api/v1/public/hospital/")
        departments = self.client.get("/api/v1/public/departments/")
        doctors = self.client.get("/api/v1/public/doctors/")
        live = self.client.get("/api/v1/health/live/")
        ready = self.client.get("/api/v1/health/ready/")
        self.assertEqual(hospital.status_code, 200)
        self.assertEqual(departments.json()[0]["name"], self.department.name)
        self.assertEqual(doctors.json()[0]["display_name"], self.doctor.display_name)
        self.assertEqual(live.json()["status"], "ok")
        self.assertEqual(live.json(), {"status": "ok"})
        self.assertEqual(ready.json()["status"], "ready")

    def test_availability_has_public_utc_and_display_times(self):
        response = self.client.get(
            f"/api/v1/public/doctors/{self.doctor.pk}/availability/",
            {"date_from": self.service_date.isoformat(), "date_to": self.service_date.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        slot = response.json()["slots"][0]
        self.assertEqual(slot["schedule_id"], str(self.schedule.pk))
        self.assertIn("+06:00", slot["display_start"])
        self.assertTrue(slot["start_at"].endswith("Z"))

    def test_errors_always_include_stable_envelope_and_request_id(self):
        supplied = str(uuid.uuid4())
        response = self.client.get("/api/v1/appointments/", HTTP_X_REQUEST_ID=supplied)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            set(response.json()),
            {"status", "code", "title", "detail", "field_errors", "request_id"},
        )
        self.assertEqual(response.json()["request_id"], supplied)
        self.assertEqual(response["X-Request-ID"], supplied)

    def test_patient_booking_is_idempotent(self):
        self.authenticate(self.patient_user)
        payload = {"schedule_id": str(self.schedule.pk), "department_id": str(self.department.pk), "start_at": self.start_at.isoformat()}
        key = str(uuid.uuid4())
        first = self.client.post("/api/v1/appointments/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
        second = self.client.post("/api/v1/appointments/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(second["Idempotency-Replayed"], "true")
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

    def test_idempotency_key_cannot_be_reused_for_another_payload(self):
        self.authenticate(self.patient_user)
        key = str(uuid.uuid4())
        base = {"schedule_id": str(self.schedule.pk), "department_id": str(self.department.pk), "start_at": self.start_at.isoformat()}
        self.assertEqual(self.client.post("/api/v1/appointments/", base, format="json", HTTP_IDEMPOTENCY_KEY=key).status_code, 201)
        base["start_at"] = (self.start_at + timedelta(minutes=15)).isoformat()
        response = self.client.post("/api/v1/appointments/", base, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "idempotency_key_reused")

    def test_patient_object_isolation_returns_not_found(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        other_user = self.create_user("isolated@example.test", "patient")
        PatientProfile.objects.create(
            hospital=self.hospital,
            user=other_user,
            full_name="Isolated Patient",
            email=other_user.email,
            phone="+8801800000044",
            date_of_birth=timezone.localdate().replace(year=1994),
            address="Synthetic",
            is_claimed=True,
        )
        self.authenticate(other_user)
        response = self.client.get(f"/api/v1/appointments/{appointment.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.patient.mrn, response.content.decode())

    def test_doctor_cannot_read_another_doctors_appointment(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        other_doctor_user = self.create_user("otherdoctor@example.test", "doctor", staff=True)
        self.authenticate(other_doctor_user)
        response = self.client.get(f"/api/v1/appointments/{appointment.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_default_deny_blocks_patient_from_admin_configuration(self):
        self.authenticate(self.patient_user)
        response = self.client.get("/api/v1/admin/schedules/")
        self.assertEqual(response.status_code, 403)

    def test_reception_check_in_replays_same_ticket(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        self.authenticate(self.reception_user)
        key = str(uuid.uuid4())
        url = f"/api/v1/reception/appointments/{appointment.pk}/check-in/"
        first = self.client.post(url, {}, format="json", HTTP_IDEMPOTENCY_KEY=key)
        second = self.client.post(url, {}, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(QueueTicket.objects.count(), 1)

    def test_queue_snapshot_does_not_expose_another_patient(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        other_user = self.create_user("ahead@example.test", "patient")
        other = PatientProfile.objects.create(
            hospital=self.hospital,
            user=other_user,
            full_name="Private Other Name",
            email=other_user.email,
            phone="+8801800000055",
            date_of_birth=timezone.localdate().replace(year=1993),
            address="Never expose this address",
            is_claimed=True,
        )
        other_appointment = book_appointment(
            self.request_for(other_user), other.pk, self.schedule.pk, self.department.pk, self.start_at + timedelta(minutes=15)
        )
        check_in(self.request_for(self.reception_user), other_appointment.pk)
        self.authenticate(self.patient_user)
        response = self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/")
        text = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], ticket.token)
        self.assertNotIn("Private Other Name", text)
        self.assertNotIn(other.mrn, text)
        self.assertNotIn(str(other_appointment.pk), text)

    def test_queue_etag_supports_private_conditional_polling(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.authenticate(self.patient_user)
        first = self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/")
        second = self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/", HTTP_IF_NONE_MATCH=first["ETag"])
        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.content, b"")
        self.assertEqual(first["Cache-Control"], "private, no-store")
        self.assertEqual(QueueEstimateRecord.objects.count(), 1)

    def test_reasoned_queue_action_and_payment_api(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.authenticate(self.reception_user)
        missing = self.client.post(f"/api/v1/queue-tickets/{ticket.pk}/defer/", {}, format="json", **self.idempotency())
        self.assertEqual(missing.status_code, 400)
        deferred = self.client.post(
            f"/api/v1/queue-tickets/{ticket.pk}/defer/",
            {"reason": "Patient requested a short delay", "reason_code": "patient_request"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(deferred.status_code, 200)
        paid = self.client.post(
            f"/api/v1/appointments/{appointment.pk}/payment/actions/", {"state": "paid_on_site", "reference": "CASH-001"}, format="json", **self.idempotency()
        )
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(paid.json()["state"], "paid_on_site")
        self.assertEqual(paid.json()["status"], "paid_on_site")
        self.assertEqual(paid.json()["patient"]["id"], str(self.patient.pk))

    def test_checked_in_appointment_contains_private_queue_link(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.authenticate(self.patient_user)
        response = self.client.get(f"/api/v1/appointments/{appointment.pk}/")
        self.assertEqual(response.json()["queue_id"], str(ticket.session_id))
        self.assertEqual(response.json()["queue"]["ticket_id"], str(ticket.pk))

    def test_doctor_schedule_and_staff_queue_current_ticket_shapes(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)

        call_next(self.request_for(self.doctor_user), ticket.session_id)
        self.authenticate(self.doctor_user)
        schedules = self.client.get("/api/v1/doctor/schedules/")
        snapshot = self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/")
        self.assertEqual(schedules.status_code, 200)
        self.assertEqual(schedules.json()[0]["id"], str(self.schedule.pk))
        self.assertEqual(snapshot.json()["current_ticket"]["id"], str(ticket.pk))
        self.assertEqual(snapshot.json()["current"]["state"], "called")

    def test_admin_staff_settings_notifications_and_deactivation_contracts(self):
        self.authenticate(self.admin_user)
        staff = self.client.get("/api/v1/admin/staff/")
        self.assertEqual(staff.status_code, 200)
        doctor_row = next(item for item in staff.json()["results"] if item["email"] == self.doctor_user.email)
        self.assertEqual(doctor_row["id"], str(self.doctor_user.pk))
        settings = self.client.get("/api/v1/admin/settings/")
        self.assertEqual(settings.status_code, 200)
        updated = self.client.patch(
            "/api/v1/admin/settings/", {"name": "Updated Test Hospital", "default_slot_duration_minutes": 25}, format="json", **self.idempotency()
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Updated Test Hospital")
        self.assertEqual(updated.json()["default_slot_duration_minutes"], 25)
        notifications = self.client.get("/api/v1/admin/notifications/")
        self.assertEqual(notifications.status_code, 200)
        schedule_deactivated = self.client.post(
            f"/api/v1/admin/schedules/{self.schedule.pk}/deactivate/",
            {"reason": "Synthetic test deactivation"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(schedule_deactivated.status_code, 200)
        deactivated = self.client.post(
            f"/api/v1/admin/departments/{self.department.pk}/deactivate/", {"reason": "Synthetic test deactivation"}, format="json", **self.idempotency()
        )
        self.assertEqual(deactivated.status_code, 200)
        self.assertFalse(deactivated.json()["is_active"])

    def test_hospital_settings_reject_invalid_timezone_and_normalize_currency(self):
        self.authenticate(self.admin_user)
        invalid = self.client.patch(
            "/api/v1/admin/settings/",
            {"timezone": "Asia/Dhakka"},
            format="json",
            **self.idempotency(),
        )
        normalized = self.client.patch(
            "/api/v1/admin/settings/",
            {"currency": "bdt"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("timezone", invalid.json()["field_errors"])
        self.assertEqual(normalized.status_code, 200)
        self.assertEqual(normalized.json()["currency"], "BDT")

    def test_frontend_consent_shape_updates_email_preferences_transactionally(self):
        self.authenticate(self.patient_user)
        initial = NotificationPreference.objects.create(user=self.patient_user)
        self.assertFalse(initial.appointment_email)
        enabled = self.client.post(
            "/api/v1/me/consents/", {"purpose": "email_notifications", "granted": True, "notice_version": "current"}, format="json", **self.idempotency()
        )
        self.assertEqual(enabled.status_code, 201)
        self.assertTrue(enabled.json()["granted"])
        initial.refresh_from_db()
        self.assertTrue(initial.appointment_email)
        self.assertTrue(initial.queue_email)

    def test_direct_preferences_cannot_bypass_versioned_email_consent(self):
        self.authenticate(self.patient_user)
        preference = NotificationPreference.objects.create(user=self.patient_user)
        response = self.client.patch(
            "/api/v1/notification-preferences/",
            {"appointment_email": True, "queue_email": True},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "consent_required")
        preference.refresh_from_db()
        self.assertFalse(preference.appointment_email)
        self.assertFalse(preference.queue_email)

    def test_assisted_consent_requires_current_notice_and_records_actor(self):
        stale = PrivacyNoticeVersion.objects.create(
            hospital=self.hospital,
            version="stale-test",
            title="Stale test notice",
            content="Synthetic stale notice",
            effective_at=timezone.now() - timedelta(days=1),
            is_published=True,
        )
        self.authenticate(self.reception_user)
        stale_response = self.client.post(
            f"/api/v1/reception/patients/{self.patient.pk}/consents/",
            {"notice_version_id": str(stale.pk), "purpose": "email_notifications", "decision": True},
            format="json",
            **self.idempotency(),
        )
        accepted = self.client.post(
            f"/api/v1/reception/patients/{self.patient.pk}/consents/",
            {"notice_version": "current", "purpose": "email_notifications", "decision": True},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(stale_response.status_code, 404)
        self.assertEqual(accepted.status_code, 201)
        consent = ConsentRecord.objects.get(pk=accepted.json()["id"])
        self.assertEqual(consent.channel, ConsentRecord.Channel.ASSISTED)
        self.assertEqual(consent.actor, self.reception_user)

    def test_branding_is_same_origin_and_pilot_locale_is_fixed(self):
        self.authenticate(self.admin_user)
        accepted = self.client.patch(
            "/api/v1/admin/settings/",
            {
                "tagline": "Care close to home",
                "logo_url": "/branding/hospital-logo.svg",
                "timezone": "Asia/Dhaka",
                "currency": "BDT",
                "patient_cancellation_cutoff_minutes": 0,
            },
            format="json",
            **self.idempotency(),
        )
        rejected = self.client.patch(
            "/api/v1/admin/settings/",
            {"logo_url": "https://external.example/logo.svg"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["logo_url"], "/branding/hospital-logo.svg")
        self.assertEqual(accepted.json()["patient_cancellation_cutoff_minutes"], 0)
        self.assertEqual(rejected.status_code, 400)

    def test_hospital_short_name_is_immutable_after_first_mrn(self):
        self.authenticate(self.admin_user)
        response = self.client.patch(
            "/api/v1/admin/settings/",
            {"short_name": "NEWHOSP"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("short_name", response.json()["field_errors"])

    def test_location_code_is_required_and_duplicate_is_rejected(self):
        self.authenticate(self.admin_user)
        missing = self.client.post(
            "/api/v1/admin/locations/",
            {"name": "Annex", "address": "Synthetic annex"},
            format="json",
            **self.idempotency(),
        )
        duplicate = self.client.post(
            "/api/v1/admin/locations/",
            {"name": "Annex", "code": self.location.code, "address": "Synthetic annex"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(missing.status_code, 400)
        self.assertIn("code", missing.json()["field_errors"])
        self.assertEqual(duplicate.status_code, 400)

    def test_reception_patient_search_requires_a_specific_query(self):
        self.authenticate(self.reception_user)
        blank = self.client.get("/api/v1/reception/patients/")
        short = self.client.get("/api/v1/reception/patients/", {"q": "S"})
        valid = self.client.get("/api/v1/reception/patients/", {"q": self.patient.mrn})
        self.assertEqual(blank.status_code, 400)
        self.assertEqual(short.status_code, 400)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["results"][0]["id"], str(self.patient.pk))

    def test_patient_queue_snapshot_etag_and_reasoned_leave_are_privacy_safe(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.authenticate(self.patient_user)
        url = f"/api/v1/queues/{ticket.session_id}/snapshot/"
        first = self.client.get(url)
        second = self.client.get(url)
        unchanged = self.client.get(url, HTTP_IF_NONE_MATCH=first["ETag"])
        self.assertEqual(first["ETag"], second["ETag"])
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()["doctor"]["display_name"], self.doctor.display_name)
        self.assertEqual(first.json()["location"]["name"], self.location.name)
        self.assertEqual(first.json()["chamber"]["name"], self.chamber.name)
        self.assertNotIn("patient", first.json())
        self.assertEqual(unchanged.status_code, 304)
        left = self.client.post(
            f"/api/v1/queue-tickets/{ticket.pk}/leave/",
            {"reason": "Unable to wait"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(left.status_code, 200)
        self.assertEqual(set(left.json()), {"ticket_id", "queue_id", "token", "state"})
        self.assertEqual(left.json()["state"], "cancelled")

    def test_queue_snapshot_prefers_current_active_ticket_over_older_terminal_ticket(self):
        first_appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        first = check_in(self.request_for(self.reception_user), first_appointment.pk)
        call_next(self.request_for(self.doctor_user), first.session_id)
        transition_ticket(self.request_for(self.doctor_user), first.pk, "start")
        transition_ticket(self.request_for(self.doctor_user), first.pk, "complete")
        second_appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at + timedelta(minutes=15),
        )
        second = check_in(self.request_for(self.reception_user), second_appointment.pk)
        self.authenticate(self.patient_user)
        snapshot = self.client.get(f"/api/v1/queues/{second.session_id}/snapshot/")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["ticket_id"], str(second.pk))
        self.assertEqual(snapshot.json()["state"], "waiting")

    def test_failed_notification_manual_retry_is_reasoned_and_dead_is_rejected(self):
        failed = enqueue_email("retry@example.test", "appointment_booked", {"url": "/patient/appointments/test"})
        failed.state = NotificationOutbox.State.FAILED
        failed.attempt_count = 1
        failed.save(update_fields=["state", "attempt_count", "updated_at"])
        dead = enqueue_email("dead@example.test", "reset_password", {"token": "synthetic-token"})
        dead.state = NotificationOutbox.State.DEAD
        dead.template_data = {}
        dead.save(update_fields=["state", "template_data", "updated_at"])
        self.authenticate(self.admin_user)
        retried = self.client.post(
            f"/api/v1/admin/notification-outbox/{failed.pk}/retry/",
            {"reason": "SMTP route restored"},
            format="json",
            **self.idempotency(),
        )
        rejected = self.client.post(
            f"/api/v1/admin/notification-outbox/{dead.pk}/retry/",
            {"reason": "Cannot replay erased token"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["state"], "pending")
        self.assertEqual(rejected.status_code, 409)

    def test_multirole_deactivation_preserves_unrelated_access(self):
        RoleAssignment.objects.create(user=self.patient_user, role=RoleAssignment.Role.RECEPTIONIST)
        self.patient_user.is_staff = True
        self.patient_user.save(update_fields=["is_staff", "updated_at"])
        self.authenticate(self.admin_user)
        staff_result = self.client.post(
            f"/api/v1/admin/staff/{self.patient_user.pk}/deactivate/",
            {"reason": "Reception assignment ended"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(staff_result.status_code, 200)
        self.patient_user.refresh_from_db()
        self.assertTrue(self.patient_user.is_active)
        self.assertTrue(self.patient_user.role_assignments.get(role=RoleAssignment.Role.PATIENT).is_active)
        self.assertFalse(self.patient_user.role_assignments.get(role=RoleAssignment.Role.RECEPTIONIST).is_active)

    def test_patient_deactivation_preserves_an_active_staff_role(self):
        RoleAssignment.objects.create(user=self.admin_user, role=RoleAssignment.Role.PATIENT)
        profile = PatientProfile.objects.create(
            hospital=self.hospital,
            user=self.admin_user,
            full_name="Administrator Patient",
            email=self.admin_user.email,
            phone="+8801800000777",
            date_of_birth=timezone.localdate().replace(year=1985),
            address="Synthetic address",
            is_claimed=True,
        )
        self.authenticate(self.reception_user)
        response = self.client.post(
            f"/api/v1/reception/patients/{profile.pk}/deactivate/",
            {"reason": "Duplicate patient profile"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(response.status_code, 200)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)
        self.assertTrue(self.admin_user.role_assignments.get(role=RoleAssignment.Role.ADMINISTRATOR).is_active)
        self.assertFalse(self.admin_user.role_assignments.get(role=RoleAssignment.Role.PATIENT).is_active)

    def test_schedule_exception_rejects_invalidating_confirmed_appointments(self):
        book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        self.authenticate(self.admin_user)
        response = self.client.post(
            "/api/v1/admin/schedule-exceptions/",
            {
                "schedule": str(self.schedule.pk),
                "service_date": self.service_date.isoformat(),
                "kind": "closed",
                "reason": "Synthetic closure",
            },
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "confirmed_appointments_invalidated")

    def test_consent_retry_is_idempotent(self):
        self.authenticate(self.patient_user)
        key = str(uuid.uuid4())
        payload = {"purpose": "email_notifications", "granted": True, "notice_version": "current"}
        first = self.client.post("/api/v1/me/consents/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
        replay = self.client.post("/api/v1/me/consents/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(self.patient.consents.filter(purpose="email_notifications").count(), 1)

    def test_staff_cannot_bypass_mfa_with_authenticated_session(self):
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        denied = client.get("/api/v1/admin/staff/")
        self.assertEqual(denied.status_code, 403)

    def test_appointment_filters_are_object_scoped(self):
        first = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        self.authenticate(self.patient_user)
        response = self.client.get("/api/v1/appointments/", {"status": "confirmed", "doctor_id": str(self.doctor.pk), "date": self.service_date.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["results"]], [str(first.pk)])

    def test_queue_dashboard_discovery_is_role_scoped_and_rich(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.authenticate(self.reception_user)
        reception = self.client.get("/api/v1/dashboards/receptionist/")
        self.assertEqual(reception.status_code, 200)
        self.assertEqual(reception.json()["recent"][0]["queue_id"], str(ticket.session_id))
        self.assertIn("waiting_count", reception.json()["recent"][0])
        self.authenticate(self.doctor_user)
        doctor = self.client.get("/api/v1/dashboards/doctor/")
        self.assertEqual(doctor.json()["recent"][0]["doctor"]["id"], str(self.doctor.pk))
        self.authenticate(self.patient_user)
        denied = self.client.get("/api/v1/dashboards/receptionist/")
        self.assertEqual(denied.status_code, 403)

    def test_notification_staff_access_requires_verified_mfa(self):
        client = APIClient()
        client.force_authenticate(user=self.doctor_user)
        self.assertEqual(client.get("/api/v1/notifications/").status_code, 403)
        session = client.session
        session["mfa_verified"] = True
        session.save()
        self.assertEqual(client.get("/api/v1/notifications/").status_code, 200)

    def test_staff_queue_identity_has_dob_and_sex_but_patient_snapshot_does_not(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.authenticate(self.doctor_user)
        staff = self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/")
        patient = staff.json()["tickets"][0]["patient"]
        self.assertIn("date_of_birth", patient)
        self.assertIn("sex", patient)
        self.authenticate(self.patient_user)
        self_snapshot = self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/")
        self.assertNotIn("patient", self_snapshot.json())
        self.assertNotIn("date_of_birth", self_snapshot.content.decode())

    def test_staff_deactivation_is_reasoned_idempotent_and_protects_self_and_patients(self):
        self.authenticate(self.admin_user)
        staff = self.client.get("/api/v1/admin/staff/")
        doctor = next(row for row in staff.json()["results"] if row["id"] == str(self.doctor_user.pk))
        self.assertEqual(doctor["doctor_profile_id"], str(self.doctor.pk))
        key = str(uuid.uuid4())
        url = f"/api/v1/admin/staff/{self.reception_user.pk}/deactivate/"
        first = self.client.post(url, {"reason": "Synthetic departure"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
        replay = self.client.post(url, {"reason": "Synthetic departure"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.reception_user.refresh_from_db()
        self.assertFalse(self.reception_user.is_active)
        self.assertTrue(AuditEvent.objects.filter(event_type="staff.deactivated", subject_id=self.reception_user.pk).exists())
        own = self.client.post(
            f"/api/v1/admin/staff/{self.admin_user.pk}/deactivate/",
            {"reason": "must be blocked"},
            format="json",
            **self.idempotency(),
        )
        patient_only = self.client.post(
            f"/api/v1/admin/staff/{self.patient_user.pk}/deactivate/",
            {"reason": "must be blocked"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(own.status_code, 409)
        self.assertEqual(patient_only.status_code, 404)

    def test_doctor_directory_deactivation_reconciles_user_roles_and_mfa(self):
        doctor_only_user = self.create_user("doctor-only@example.test", "doctor", staff=True)
        doctor_only = DoctorProfile.objects.create(
            hospital=self.hospital,
            user=doctor_only_user,
            doctor_code="D010",
            display_name="Dr Doctor Only",
            designation="Consultant",
        )
        doctor_only.departments.add(self.department)
        doctor_only_device = StaffMFADevice(user=doctor_only_user, confirmed_at=timezone.now())
        doctor_only_device.set_secret("JBSWY3DPEHPK3PXP")
        doctor_only_device.save()

        multi_user = self.create_user("doctor-patient@example.test", "doctor", staff=True)
        RoleAssignment.objects.create(user=multi_user, role=RoleAssignment.Role.PATIENT)
        multi_doctor = DoctorProfile.objects.create(
            hospital=self.hospital,
            user=multi_user,
            doctor_code="D011",
            display_name="Dr Patient Role",
            designation="Consultant",
        )
        multi_doctor.departments.add(self.department)
        PatientProfile.objects.create(
            hospital=self.hospital,
            user=multi_user,
            full_name="Doctor Patient Synthetic",
            email=multi_user.email,
            phone="+8801800000077",
            date_of_birth=timezone.localdate().replace(year=1984),
            address="Synthetic address",
            is_claimed=True,
        )
        multi_device = StaffMFADevice(user=multi_user, confirmed_at=timezone.now())
        multi_device.set_secret("KRSXG5DSNFXGOIDB")
        multi_device.save()

        self.authenticate(self.admin_user)
        for profile in (doctor_only, multi_doctor):
            response = self.client.post(
                f"/api/v1/admin/doctors/{profile.pk}/deactivate/",
                {"reason": "Synthetic role reconciliation"},
                format="json",
                **self.idempotency(),
            )
            self.assertEqual(response.status_code, 200)

        doctor_only_user.refresh_from_db()
        doctor_only_device.refresh_from_db()
        self.assertFalse(doctor_only_user.is_active)
        self.assertIsNotNone(doctor_only_device.revoked_at)
        multi_user.refresh_from_db()
        multi_device.refresh_from_db()
        self.assertTrue(multi_user.is_active)
        self.assertTrue(
            multi_user.role_assignments.get(role=RoleAssignment.Role.PATIENT).is_active
        )
        self.assertIsNotNone(multi_device.revoked_at)

    def test_configuration_and_schedule_updates_record_safe_before_and_after(self):
        self.authenticate(self.admin_user)
        department = self.client.patch(
            f"/api/v1/admin/departments/{self.department.pk}/",
            {"name": "Family Medicine"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(department.status_code, 200)
        configuration_event = AuditEvent.objects.filter(
            event_type="configuration.updated",
            subject_id=self.department.pk,
        ).latest("created_at")
        self.assertEqual(configuration_event.changes["before"]["name"], "General Medicine")
        self.assertEqual(configuration_event.changes["after"]["name"], "Family Medicine")

        schedule = self.client.patch(
            f"/api/v1/admin/schedules/{self.schedule.pk}/",
            {"capacity_per_slot": 2},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(schedule.status_code, 200)
        schedule_event = AuditEvent.objects.filter(
            event_type="schedule.updated",
            subject_id=self.schedule.pk,
        ).latest("created_at")
        self.assertEqual(schedule_event.changes["before"]["capacity_per_slot"], 1)
        self.assertEqual(schedule_event.changes["after"]["capacity_per_slot"], 2)

    def test_schedule_update_preserves_existing_appointment_identity_and_capacity(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        self.authenticate(self.admin_user)

        structural_change = self.client.patch(
            f"/api/v1/admin/schedules/{self.schedule.pk}/",
            {"start_local": "08:30:00"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(structural_change.status_code, 409)
        self.assertEqual(structural_change.json()["code"], "schedule_has_appointments")
        self.schedule.refresh_from_db()
        appointment.refresh_from_db()
        self.assertEqual(self.schedule.start_local.isoformat(), "09:00:00")
        self.assertEqual(appointment.start_at, self.start_at)
        self.assertEqual(appointment.doctor_id, self.doctor.pk)
        self.assertEqual(appointment.chamber_id, self.chamber.pk)

        capacity_increase = self.client.patch(
            f"/api/v1/admin/schedules/{self.schedule.pk}/",
            {"capacity_per_slot": 2},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(capacity_increase.status_code, 200)

        second_user = self.create_user("schedule-integrity@example.test", "patient")
        second_patient = PatientProfile.objects.create(
            hospital=self.hospital,
            user=second_user,
            full_name="Schedule Integrity Patient",
            email=second_user.email,
            phone="+8801800000088",
            date_of_birth=timezone.localdate().replace(year=1992),
            address="Synthetic address",
            is_claimed=True,
        )
        book_appointment(
            self.request_for(second_user),
            second_patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )

        capacity_reduction = self.client.patch(
            f"/api/v1/admin/schedules/{self.schedule.pk}/",
            {"capacity_per_slot": 1},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(capacity_reduction.status_code, 409)
        self.assertEqual(capacity_reduction.json()["code"], "capacity_below_confirmed")
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.capacity_per_slot, 2)

    def test_bounded_lists_expose_second_pages(self):
        for index in range(3):
            Notification.objects.create(
                user=self.patient_user,
                category="test",
                title=f"Notification {index}",
                body="Synthetic notification",
            )
            enqueue_email(
                f"failed{index}@example.test",
                "appointment_booked",
                {"url": "/synthetic"},
            )
            AuditEvent.objects.create(
                event_type=f"synthetic.page.{index}",
                actor=self.admin_user,
                actor_role="administrator",
                subject_type="system",
                action="test",
                request_id=uuid.uuid4(),
            )
        NotificationOutbox.objects.update(state=NotificationOutbox.State.FAILED)

        self.authenticate(self.patient_user)
        notifications = self.client.get("/api/v1/notifications/", {"page": 2, "page_size": 2})
        self.assertEqual(notifications.status_code, 200)
        self.assertEqual(notifications.json()["count"], 3)
        self.assertEqual(len(notifications.json()["results"]), 1)

        self.authenticate(self.admin_user)
        outbox = self.client.get("/api/v1/admin/notification-outbox/", {"page": 2, "page_size": 2})
        staff = self.client.get("/api/v1/admin/staff/", {"page": 2, "page_size": 2})
        audit_events = self.client.get("/api/v1/admin/audit-events/", {"page": 2, "page_size": 2})
        self.assertEqual(outbox.json()["count"], 3)
        self.assertEqual(len(outbox.json()["results"]), 1)
        self.assertGreaterEqual(staff.json()["count"], 3)
        self.assertTrue(staff.json()["results"])
        self.assertGreaterEqual(audit_events.json()["count"], 3)
        self.assertTrue(audit_events.json()["results"])

    def test_audit_filters_actor_and_time_with_bounded_validation(self):
        AuditEvent.objects.create(
            event_type="synthetic.audit.target",
            actor=self.admin_user,
            actor_role="administrator",
            subject_type="system",
            action="test",
            request_id=uuid.uuid4(),
        )
        self.authenticate(self.admin_user)
        response = self.client.get(
            "/api/v1/admin/audit-events/",
            {
                "actor": self.admin_user.email,
                "from": (timezone.now() - timedelta(minutes=1)).isoformat(),
                "to": (timezone.now() + timedelta(minutes=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(item["event_type"] == "synthetic.audit.target" for item in response.json()["results"]))
        self.assertEqual(self.client.get("/api/v1/admin/audit-events/", {"actor": "not-an-actor"}).status_code, 400)
        self.assertEqual(self.client.get("/api/v1/admin/audit-events/", {"from": "2026-08-14", "to": "2025-08-14"}).status_code, 400)

    def test_queue_polling_persists_only_initial_estimate_and_bounds_access_audit(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.assertEqual(QueueEstimateRecord.objects.filter(ticket=ticket).count(), 1)
        self.authenticate(self.doctor_user)
        for _ in range(3):
            self.client.get(f"/api/v1/queues/{ticket.session_id}/snapshot/")
        self.assertEqual(QueueEstimateRecord.objects.filter(ticket=ticket).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(event_type="queue.identity_viewed", subject_id=ticket.session_id, actor=self.doctor_user).count(), 1)

    def test_schedule_deactivation_removes_public_availability(self):
        self.location.is_active = False
        self.location.save(update_fields=["is_active", "updated_at"])
        response = self.client.get(
            f"/api/v1/public/doctors/{self.doctor.pk}/availability/",
            {"date_from": self.service_date.isoformat(), "date_to": self.service_date.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"], [])

    def test_check_in_rejects_future_date_and_marks_late_same_day_without_reordering(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        future_start = self.start_at + timedelta(days=1)
        appointment.start_at = future_start
        appointment.end_at = future_start + timedelta(minutes=15)
        appointment.save(update_fields=["start_at", "end_at", "updated_at"])
        with self.assertRaises(Exception) as caught:
            check_in(self.request_for(self.reception_user), appointment.pk)
        self.assertEqual(caught.exception.get_codes(), "check_in_wrong_date")
        fixed_now = self.start_at + timedelta(hours=2)
        appointment.start_at = fixed_now - timedelta(minutes=16)
        appointment.end_at = fixed_now - timedelta(minutes=1)
        appointment.save(update_fields=["start_at", "end_at", "updated_at"])
        from unittest.mock import patch

        with patch("operations.services.timezone.now", return_value=fixed_now):
            ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.assertTrue(ticket.was_late)
        self.assertEqual(ticket.late_by_minutes, 16)

    def test_terminal_appointment_cannot_collect_payment(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])
        self.authenticate(self.reception_user)
        response = self.client.post(
            f"/api/v1/appointments/{appointment.pk}/payment/actions/",
            {"state": "paid_on_site", "reference": "TEST-RECEIPT-1"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "appointment_not_payable")

    def test_payment_is_least_privilege_and_rejects_missing_or_card_like_reference(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        self.authenticate(self.doctor_user)
        denied = self.client.get(f"/api/v1/appointments/{appointment.pk}/payment/")
        self.assertEqual(denied.status_code, 404)

        self.authenticate(self.reception_user)
        missing = self.client.post(
            f"/api/v1/appointments/{appointment.pk}/payment/actions/",
            {"state": "paid_on_site"},
            format="json",
            **self.idempotency(),
        )
        card_like = self.client.post(
            f"/api/v1/appointments/{appointment.pk}/payment/actions/",
            {"state": "paid_on_site", "reference": "4111 1111 1111 1111"},
            format="json",
            **self.idempotency(),
        )
        self.assertEqual(missing.status_code, 400)
        self.assertIn("reference", missing.json()["field_errors"])
        self.assertEqual(card_like.status_code, 400)
        self.assertIn("reference", card_like.json()["field_errors"])


class SessionAndCSRFSecurityTests(HospitalTestCase):
    def test_anonymous_session_has_fixed_safe_shape(self):
        response = APIClient().get("/api/v1/auth/session/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False, "user": None, "roles": [], "mfa_verified": False, "permissions": []})

    def test_public_login_requires_csrf_when_checks_are_enabled(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post("/api/v1/auth/login/", {"email": self.patient_user.email, "password": self.password}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "csrf_failed")
        bootstrap = client.get("/api/v1/auth/csrf/")
        token = bootstrap.json()["csrf_token"]
        accepted = client.post("/api/v1/auth/login/", {"email": self.patient_user.email, "password": self.password}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["authenticated"])

    def test_five_failed_logins_temporarily_lock_account(self):
        client = APIClient()
        for _ in range(5):
            self.assertEqual(
                client.post("/api/v1/auth/login/", {"email": self.patient_user.email, "password": "WrongPassword!2026"}, format="json").status_code, 401
            )
        locked = client.post("/api/v1/auth/login/", {"email": self.patient_user.email, "password": self.password}, format="json")
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.json()["code"], "account_temporarily_locked")
