import io
import json
from datetime import time, timedelta
from unittest.mock import patch
from urllib import error

from django.test import override_settings
from django.utils import timezone

from directory.models import DoctorProfile, PatientProfile
from help_assistant.services import answer_question
from operations.models import Appointment, PaymentRecord, QueueSession, QueueTicket, Schedule
from operations.tests.base import HospitalTestCase


class AssistantAPITests(HospitalTestCase):
    endpoint = "/api/v1/assistant/chat/"

    def staff_sign_in(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["mfa_verified"] = True
        session.save()

    def create_appointment(self, patient, doctor=None, days=1, amount=75000):
        doctor = doctor or self.doctor
        start_at = timezone.now() + timedelta(days=days)
        appointment = Appointment.objects.create(
            hospital=self.hospital,
            patient=patient,
            doctor=doctor,
            department=self.department,
            location=self.location,
            chamber=self.chamber,
            schedule=self.schedule,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=15),
            source=Appointment.Source.PATIENT,
            booking_actor=patient.user or self.reception_user,
        )
        PaymentRecord.objects.create(appointment=appointment, amount_minor=amount)
        return appointment

    def test_authentication_validation_and_staff_mfa_are_enforced(self):
        response = self.client.post(self.endpoint, {"message": "How do appointments work?"}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.admin_user)
        response = self.client.post(self.endpoint, {"message": "Give me a summary"}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.staff_sign_in(self.admin_user)
        response = self.client.post(self.endpoint, {"message": "x"}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.endpoint,
            {"message": "Explain the system", "unexpected": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patient_receives_only_their_live_appointment_and_payment(self):
        own = self.create_appointment(self.patient)
        other_user = self.create_user("other@example.test", "patient")
        other = PatientProfile.objects.create(
            hospital=self.hospital,
            user=other_user,
            full_name="Private Other Patient",
            email=other_user.email,
            phone="+8801800000099",
            date_of_birth=timezone.localdate().replace(year=1985),
            address="Synthetic address",
            is_claimed=True,
        )
        other_doctor_user = self.create_user("other-doctor@example.test", "doctor", staff=True)
        other_doctor = DoctorProfile.objects.create(
            hospital=self.hospital,
            user=other_doctor_user,
            doctor_code="D099",
            display_name="Dr Private Other",
            designation="Consultant",
        )
        other_doctor.departments.add(self.department)
        self.create_appointment(other, doctor=other_doctor, days=2)
        self.client.force_login(self.patient_user)
        response = self.client.post(self.endpoint, {"message": "What is my next appointment?"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(self.doctor.display_name, body["answer"])
        self.assertNotIn("Dr Private Other", body["answer"])
        self.assertNotIn("Private Other Patient", json.dumps(body))
        self.assertTrue(body["live_data"])
        payment = self.client.post(self.endpoint, {"message": "What is my payment?"}, content_type="application/json").json()
        self.assertIn("BDT 750.00", payment["answer"])
        self.assertEqual(own.payment.amount_minor, 75000)

    def test_patient_queue_answer_uses_only_the_signed_in_ticket(self):
        appointment = self.create_appointment(self.patient)
        session = QueueSession.objects.create(
            doctor=self.doctor,
            location=self.location,
            chamber=self.chamber,
            service_date=timezone.localdate(),
        )
        ticket = QueueTicket.objects.create(
            appointment=appointment,
            session=session,
            token="A002",
            token_sequence=2,
            checked_in_at=timezone.now(),
            effective_waiting_at=timezone.now(),
            last_transition_at=timezone.now(),
        )
        self.client.force_login(self.patient_user)
        response = self.client.post(self.endpoint, {"message": "Where is my queue token?"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(ticket.token, response.json()["answer"])
        self.assertEqual(response.json()["actions"][0]["path"], f"/patient/queue/{session.pk}")

    def test_live_doctor_availability_is_calculated_from_capacity(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        Schedule.objects.create(
            hospital=self.hospital,
            doctor=self.doctor,
            location=self.location,
            chamber=self.chamber,
            weekday=tomorrow.weekday(),
            start_local=time(14, 0),
            end_local=time(15, 0),
            slot_duration_minutes=15,
            capacity_per_slot=2,
            effective_from=timezone.localdate(),
        )
        self.client.force_login(self.patient_user)
        response = self.client.post(
            self.endpoint,
            {"message": f"Is {self.doctor.display_name} available tomorrow?"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(tomorrow.isoformat(), body["answer"])
        self.assertIn("open place", body["answer"])
        self.assertTrue(body["live_data"])
        self.assertEqual(body["provider"], "local")

    def test_doctor_pressure_and_queue_are_scoped_to_their_profile(self):
        self.create_appointment(self.patient)
        self.staff_sign_in(self.doctor_user)
        pressure = self.client.post(
            self.endpoint,
            {"message": "When is my patient pressure low?"},
            content_type="application/json",
        )
        self.assertEqual(pressure.status_code, 200)
        self.assertIn("confirmed appointment", pressure.json()["answer"])
        queue = self.client.post(
            self.endpoint,
            {"message": "How many patients are waiting today?"},
            content_type="application/json",
        )
        self.assertEqual(queue.status_code, 200)
        self.assertIn("No queue session", queue.json()["answer"])

    def test_reception_and_administrator_receive_aggregate_answers(self):
        self.create_appointment(self.patient, days=0)
        self.staff_sign_in(self.reception_user)
        reception = self.client.post(
            self.endpoint,
            {"message": "How many patients are waiting today?"},
            content_type="application/json",
        )
        self.assertEqual(reception.status_code, 200)
        self.assertIn("operational totals", reception.json()["answer"])
        self.staff_sign_in(self.admin_user)
        admin = self.client.post(
            self.endpoint,
            {"message": "Which doctor has low pressure this week?"},
            content_type="application/json",
        )
        self.assertEqual(admin.status_code, 200)
        self.assertIn(self.doctor.display_name, admin.json()["answer"])

    def test_clinical_questions_are_refused_without_calling_provider(self):
        self.client.force_login(self.patient_user)
        with patch("help_assistant.services._groq_answer") as provider:
            response = self.client.post(
                self.endpoint,
                {"message": "Can you diagnose my chest pain?"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("cannot assess symptoms", response.json()["answer"])
        provider.assert_not_called()

    @override_settings(GROQ_API_KEY="synthetic-key", GROQ_TIMEOUT_SECONDS=2)
    def test_provider_failure_returns_local_help_without_exposing_error(self):
        self.client.force_login(self.patient_user)
        with patch("help_assistant.services.request.urlopen", side_effect=error.URLError("offline")):
            response = self.client.post(
                self.endpoint,
                {"message": "Explain privacy choices"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "local")
        self.assertIn("role based", response.json()["answer"])
        self.assertNotIn("offline", json.dumps(response.json()))

    @override_settings(GROQ_API_KEY="synthetic-key", GROQ_MODEL="synthetic-model", GROQ_TIMEOUT_SECONDS=2)
    def test_safe_general_question_can_use_groq_response(self):
        class SyntheticResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        provider_body = json.dumps({"choices": [{"message": {"content": "Open Privacy choices to review your settings."}}]}).encode()
        self.client.force_login(self.patient_user)
        with patch("help_assistant.services.request.urlopen", return_value=SyntheticResponse(provider_body)) as provider:
            response = self.client.post(
                self.endpoint,
                {"message": "Where are privacy choices?", "history": [{"role": "assistant", "content": "How can I help?"}]},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "groq")
        self.assertIn("Open Privacy choices", response.json()["answer"])
        sent = json.loads(provider.call_args.args[0].data)
        self.assertEqual(sent["model"], "synthetic-model")
        self.assertNotIn(self.patient.full_name, json.dumps(sent))
        self.assertNotIn("How can I help?", json.dumps(sent))

    def test_private_identifiers_are_not_sent_to_groq(self):
        with override_settings(GROQ_API_KEY="synthetic-key"):
            with patch("help_assistant.services.request.urlopen") as provider:
                result = answer_question(self.patient_user, "My email is person@example.test. Explain the system.")
        self.assertEqual(result["provider"], "local")
        provider.assert_not_called()

    def test_each_role_has_direct_workflow_guidance(self):
        patient = answer_question(self.patient_user, "How does the live queue work?")
        doctor = answer_question(self.doctor_user, "How do I defer and restore a queue token?")
        reception = answer_question(self.reception_user, "How do I check in a patient?")
        walk_in = answer_question(self.reception_user, "How do I register a walk in?")
        correction = answer_question(self.reception_user, "How do I correct a duplicate patient record?")
        admin = answer_question(self.admin_user, "How do I add a doctor and schedule?")
        audit = answer_question(self.admin_user, "What can I inspect in the audit trail?")
        self.assertIn("Reception issues", patient["answer"])
        self.assertIn("Defer", doctor["answer"])
        self.assertIn("Check in", reception["answer"])
        self.assertIn("walk in", walk_in["answer"])
        self.assertIn("possible duplicate", correction["answer"])
        self.assertIn("department", admin["answer"])
        self.assertIn("immutable", audit["answer"])

    def test_long_history_is_rejected(self):
        self.client.force_login(self.patient_user)
        response = self.client.post(
            self.endpoint,
            {
                "message": "Explain the system",
                "history": [{"role": "user", "content": f"Question {index}"} for index in range(7)],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
