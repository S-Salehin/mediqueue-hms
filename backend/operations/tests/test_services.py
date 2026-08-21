from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from communications.models import Notification, NotificationOutbox
from core.exceptions import Conflict
from core.models import AuditEvent
from directory.models import PatientProfile
from operations.models import Appointment, AppointmentHistory, PaymentHistory, PaymentRecord, QueueEvent, QueueTicket
from operations.serializers import ScheduleSerializer
from operations.services import (
    available_slots,
    book_appointment,
    calculate_estimate,
    call_next,
    cancel_appointment,
    change_payment,
    check_in,
    reschedule_appointment,
    transition_ticket,
)

from .base import HospitalTestCase


class DirectoryAndBookingTests(HospitalTestCase):
    def test_mrn_generation_is_monotonic_and_not_a_database_id(self):
        second = PatientProfile.objects.create(
            hospital=self.hospital,
            full_name="Second Synthetic Patient",
            phone="+8801800000002",
            date_of_birth=timezone.localdate().replace(year=1991),
            address="Synthetic address",
        )
        self.assertEqual(self.patient.mrn, "MRN-TCH-0000001")
        self.assertEqual(second.mrn, "MRN-TCH-0000002")
        self.assertNotIn(str(second.pk), second.mrn)

    def test_operational_identifiers_normalize_to_bounded_ascii_codes(self):
        self.location.code = "main2"
        self.location.save(update_fields=["code", "updated_at"])
        self.doctor.doctor_code = "d009"
        self.doctor.save(update_fields=["doctor_code", "updated_at"])
        self.location.refresh_from_db()
        self.doctor.refresh_from_db()
        self.assertEqual(self.location.code, "MAIN2")
        self.assertEqual(self.doctor.doctor_code, "D009")
        self.location.code = "unsafe code"
        with self.assertRaises(DjangoValidationError):
            self.location.save(update_fields=["code", "updated_at"])

    def test_availability_returns_exact_slots_and_capacity(self):
        slots = available_slots(self.doctor, self.service_date, self.service_date)
        self.assertEqual(len(slots), 12)
        self.assertEqual(slots[0]["start_at"], self.start_at)
        self.assertEqual(slots[0]["available_capacity"], 1)

    def test_schedule_serializer_rejects_inactive_operational_dependencies(self):
        self.location.is_active = False
        self.location.save(update_fields=["is_active", "updated_at"])
        serializer = ScheduleSerializer(
            data={
                "hospital": str(self.hospital.pk),
                "doctor": str(self.doctor.pk),
                "location": str(self.location.pk),
                "chamber": str(self.chamber.pk),
                "weekday": self.service_date.weekday(),
                "start_local": "13:00:00",
                "end_local": "14:00:00",
                "slot_duration_minutes": 15,
                "capacity_per_slot": 1,
                "effective_from": timezone.localdate().isoformat(),
                "is_active": True,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("location", serializer.errors)

    def test_booking_commits_business_side_effects(self):
        request = self.request_for(self.patient_user)
        appointment = book_appointment(request, self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertEqual(appointment.source, Appointment.Source.PATIENT)
        self.assertEqual(AppointmentHistory.objects.filter(appointment=appointment, event="created").count(), 1)
        self.assertEqual(PaymentRecord.objects.get(appointment=appointment).amount_minor, 75000)
        self.assertTrue(AuditEvent.objects.filter(subject_id=appointment.pk, event_type="appointment.created").exists())
        self.assertTrue(Notification.objects.filter(related_id=appointment.pk, category="appointment").exists())
        self.assertFalse(NotificationOutbox.objects.filter(related_id=appointment.pk, template_key="appointment_booked").exists())

    def test_capacity_is_checked_inside_locked_booking(self):
        book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        other_user = self.create_user("other@example.test", "patient")
        other = PatientProfile.objects.create(
            hospital=self.hospital,
            user=other_user,
            full_name="Other Synthetic Patient",
            email=other_user.email,
            phone="+8801800000009",
            date_of_birth=timezone.localdate().replace(year=1995),
            address="Synthetic address",
            is_claimed=True,
        )
        with self.assertRaises(Conflict) as caught:
            book_appointment(self.request_for(other_user), other.pk, self.schedule.pk, self.department.pk, self.start_at)
        self.assertEqual(caught.exception.get_codes(), "slot_full")
        self.assertEqual(Appointment.objects.count(), 1)

    def test_patient_cannot_book_for_another_patient(self):
        other = PatientProfile.objects.create(
            hospital=self.hospital,
            full_name="Other Synthetic Patient",
            phone="+8801800000009",
            date_of_birth=timezone.localdate().replace(year=1995),
            address="Synthetic address",
        )
        with self.assertRaises(Exception):
            book_appointment(self.request_for(self.patient_user), other.pk, self.schedule.pk, self.department.pk, self.start_at)
        self.assertFalse(Appointment.objects.exists())

    def test_reschedule_updates_allocation_and_keeps_confirmed_state(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        next_slot = self.start_at + timedelta(minutes=15)
        updated = reschedule_appointment(
            self.request_for(self.patient_user), appointment.pk, self.schedule.pk, self.department.pk, next_slot, "Patient selected a later time"
        )
        self.assertEqual(updated.start_at, next_slot)
        self.assertEqual(updated.status, Appointment.Status.CONFIRMED)
        self.assertTrue(updated.history.filter(event="rescheduled").exists())

    def test_reschedule_updates_unpaid_fee_with_append_only_history(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        self.doctor.consultation_fee_minor = 90000
        self.doctor.save(update_fields=["consultation_fee_minor", "updated_at"])
        updated = reschedule_appointment(
            self.request_for(self.reception_user),
            appointment.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at + timedelta(minutes=15),
            "Doctor fee changed before collection",
        )
        payment = updated.payment
        payment.refresh_from_db()
        self.assertEqual(payment.amount_minor, 90000)
        history = PaymentHistory.objects.get(payment=payment)
        self.assertEqual(history.previous_amount_minor, 75000)
        self.assertEqual(history.new_amount_minor, 90000)

    def test_reschedule_rejects_different_fee_after_payment(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        change_payment(
            self.request_for(self.reception_user),
            appointment.pk,
            PaymentRecord.State.PAID_ON_SITE,
            reference="COUNTER-2026-0001",
        )
        self.doctor.consultation_fee_minor = 90000
        self.doctor.save(update_fields=["consultation_fee_minor", "updated_at"])
        with self.assertRaises(Conflict) as caught:
            reschedule_appointment(
                self.request_for(self.reception_user),
                appointment.pk,
                self.schedule.pk,
                self.department.pk,
                self.start_at + timedelta(minutes=15),
                "Requested another time",
            )
        self.assertEqual(caught.exception.get_codes(), "payment_correction_required")
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, self.start_at)

    def test_zero_cutoff_allows_patient_change_before_start_but_never_at_start(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        self.hospital.operational_settings = {"patient_cancellation_cutoff_minutes": 0}
        self.hospital.save(update_fields=["operational_settings", "updated_at"])
        with patch("operations.services.timezone.now", return_value=self.start_at - timedelta(seconds=1)):
            cancelled = cancel_appointment(
                self.request_for(self.patient_user),
                appointment.pk,
                "Patient cancelled before the start",
            )
        self.assertEqual(cancelled.status, Appointment.Status.CANCELLED)

        second_start = self.start_at + timedelta(minutes=15)
        second = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            second_start,
        )
        with patch("operations.services.timezone.now", return_value=second_start):
            with self.assertRaises(Conflict) as caught:
                cancel_appointment(
                    self.request_for(self.patient_user),
                    second.pk,
                    "Too late",
                )
        self.assertEqual(caught.exception.get_codes(), "patient_cancellation_closed")

    def test_positive_patient_cutoff_closes_changes_at_the_boundary(self):
        appointment = book_appointment(
            self.request_for(self.patient_user),
            self.patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at,
        )
        self.hospital.operational_settings = {"patient_cancellation_cutoff_minutes": 60}
        self.hospital.save(update_fields=["operational_settings", "updated_at"])
        with patch("operations.services.timezone.now", return_value=self.start_at - timedelta(minutes=60)):
            with self.assertRaises(Conflict) as caught:
                reschedule_appointment(
                    self.request_for(self.patient_user),
                    appointment.pk,
                    self.schedule.pk,
                    self.department.pk,
                    self.start_at + timedelta(minutes=15),
                    "Patient requested later",
                )
        self.assertEqual(caught.exception.get_codes(), "patient_reschedule_closed")

    def test_cancel_is_terminal_and_preserves_history(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        cancel_appointment(self.request_for(self.patient_user), appointment.pk, "Plans changed")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        with self.assertRaises(Conflict):
            cancel_appointment(self.request_for(self.patient_user), appointment.pk, "Repeated")
        self.assertEqual(appointment.history.filter(event="cancelled").count(), 1)


class QueueServiceTests(HospitalTestCase):
    def make_appointment(self, patient=None, start_offset=0):
        patient = patient or self.patient
        return book_appointment(
            self.request_for(patient.user or self.reception_user),
            patient.pk,
            self.schedule.pk,
            self.department.pk,
            self.start_at + timedelta(minutes=start_offset),
        )

    def test_check_in_allocates_final_token_once(self):
        appointment = self.make_appointment()
        ticket = check_in(self.request_for(self.reception_user), appointment.pk)
        self.assertEqual(ticket.token, "D001-001")
        self.assertEqual(ticket.state, QueueTicket.State.WAITING)
        with self.assertRaises(Conflict):
            check_in(self.request_for(self.reception_user), appointment.pk)
        self.assertEqual(QueueEvent.objects.filter(ticket=ticket).count(), 1)

    def test_call_next_uses_fifo_and_prevents_second_active_ticket(self):
        first = check_in(self.request_for(self.reception_user), self.make_appointment().pk)
        other_user = self.create_user("queue2@example.test", "patient")
        other = PatientProfile.objects.create(
            hospital=self.hospital,
            user=other_user,
            full_name="Queue Patient Two",
            email=other_user.email,
            phone="+8801800000022",
            date_of_birth=timezone.localdate().replace(year=1992),
            address="Synthetic",
            is_claimed=True,
        )
        second = check_in(self.request_for(self.reception_user), self.make_appointment(other, 15).pk)
        called = call_next(self.request_for(self.doctor_user), first.session_id)
        self.assertEqual(called.pk, first.pk)
        with self.assertRaises(Conflict):
            call_next(self.request_for(self.doctor_user), first.session_id)
        second.refresh_from_db()
        self.assertEqual(second.state, QueueTicket.State.WAITING)

    def test_defer_requires_reason_and_restore_rejoins_at_current_time(self):
        ticket = check_in(self.request_for(self.reception_user), self.make_appointment().pk)
        with self.assertRaises(ValidationError):
            transition_ticket(self.request_for(self.doctor_user), ticket.pk, "defer", "")
        transition_ticket(self.request_for(self.doctor_user), ticket.pk, "defer", "Patient asked for a short delay", "patient_request")
        original_wait = ticket.effective_waiting_at
        restored = transition_ticket(self.request_for(self.doctor_user), ticket.pk, "restore", "Patient returned", "returned")
        self.assertEqual(restored.state, QueueTicket.State.WAITING)
        self.assertGreater(restored.effective_waiting_at, original_wait)

    def test_complete_updates_appointment_atomically(self):
        ticket = check_in(self.request_for(self.reception_user), self.make_appointment().pk)
        call_next(self.request_for(self.doctor_user), ticket.session_id)
        transition_ticket(self.request_for(self.doctor_user), ticket.pk, "start")
        completed = transition_ticket(self.request_for(self.doctor_user), ticket.pk, "complete")
        completed.appointment.refresh_from_db()
        self.assertEqual(completed.state, QueueTicket.State.COMPLETED)
        self.assertEqual(completed.appointment.status, Appointment.Status.COMPLETED)
        self.assertTrue(completed.appointment.history.filter(event="completed").exists())

    def test_illegal_transition_has_no_side_effect(self):
        ticket = check_in(self.request_for(self.reception_user), self.make_appointment().pk)
        with self.assertRaises(Conflict):
            transition_ticket(self.request_for(self.doctor_user), ticket.pk, "complete")
        ticket.refresh_from_db()
        self.assertEqual(ticket.state, QueueTicket.State.WAITING)

    def test_no_show_is_terminal_and_requires_reason(self):
        ticket = check_in(self.request_for(self.reception_user), self.make_appointment().pk)
        transition_ticket(self.request_for(self.reception_user), ticket.pk, "no_show", "Patient did not respond", "not_present")
        ticket.refresh_from_db()
        ticket.appointment.refresh_from_db()
        self.assertEqual(ticket.state, QueueTicket.State.NO_SHOW)
        self.assertEqual(ticket.appointment.status, Appointment.Status.NO_SHOW)
        with self.assertRaises(Conflict):
            transition_ticket(self.request_for(self.reception_user), ticket.pk, "restore", "Returned")


class EstimateAndPaymentTests(HospitalTestCase):
    def make_waiting_ticket(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        return check_in(self.request_for(self.reception_user), appointment.pk)

    def add_completed_sample(self, session, index, duration_minutes):
        patient = PatientProfile.objects.create(
            hospital=self.hospital,
            full_name=f"Sample Patient {index}",
            phone=f"+8801900000{index:03d}",
            date_of_birth=timezone.localdate().replace(year=1985),
            address="Synthetic",
        )
        appointment = Appointment.objects.create(
            hospital=self.hospital,
            patient=patient,
            doctor=self.doctor,
            department=self.department,
            location=self.location,
            chamber=self.chamber,
            schedule=self.schedule,
            start_at=self.start_at + timedelta(days=index),
            end_at=self.start_at + timedelta(days=index, minutes=15),
            source=Appointment.Source.RECEPTION,
            status=Appointment.Status.COMPLETED,
            booking_actor=self.reception_user,
        )
        ended = timezone.now() - timedelta(days=index)
        return QueueTicket.objects.create(
            appointment=appointment,
            session=session,
            token=f"S-{index:03d}",
            token_sequence=100 + index,
            checked_in_at=ended - timedelta(minutes=duration_minutes + 5),
            effective_waiting_at=ended - timedelta(minutes=duration_minutes + 5),
            state=QueueTicket.State.COMPLETED,
            service_started_at=ended - timedelta(minutes=duration_minutes),
            service_ended_at=ended,
            last_transition_at=ended,
        )

    def test_estimate_uses_configured_fallback_below_five_samples(self):
        ticket = self.make_waiting_ticket()
        result = calculate_estimate(ticket, persist=False)
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["point_wait_minutes"], 0)
        self.assertEqual((result["wait_lower_minutes"], result["wait_upper_minutes"]), (0, 5))

    def test_estimate_uses_weighted_median_at_five_samples(self):
        ticket = self.make_waiting_ticket()
        for index, duration in enumerate([10, 20, 20, 30, 40], 1):
            self.add_completed_sample(ticket.session, index, duration)
        active_patient = PatientProfile.objects.create(
            hospital=self.hospital,
            full_name="Active Synthetic Patient",
            phone="+8801900099999",
            date_of_birth=timezone.localdate().replace(year=1988),
            address="Synthetic",
        )
        active_appointment = Appointment.objects.create(
            hospital=self.hospital,
            patient=active_patient,
            doctor=self.doctor,
            department=self.department,
            location=self.location,
            chamber=self.chamber,
            schedule=self.schedule,
            start_at=self.start_at + timedelta(days=20),
            end_at=self.start_at + timedelta(days=20, minutes=15),
            source=Appointment.Source.RECEPTION,
            booking_actor=self.reception_user,
        )
        now = timezone.now()
        active = QueueTicket.objects.create(
            appointment=active_appointment,
            session=ticket.session,
            token="ACTIVE-1",
            token_sequence=99,
            checked_in_at=now - timedelta(minutes=10),
            effective_waiting_at=now - timedelta(minutes=10),
            state=QueueTicket.State.IN_SERVICE,
            service_started_at=now - timedelta(minutes=5),
            last_transition_at=now - timedelta(minutes=5),
        )
        ticket.session.active_ticket = active
        ticket.session.save(update_fields=["active_ticket", "updated_at"])
        result = calculate_estimate(ticket, now=now, persist=True)
        self.assertEqual(result["confidence"], "medium")
        self.assertEqual(result["sample_count"], 5)
        self.assertEqual(result["point_wait_minutes"], 14)
        self.assertGreaterEqual(result["wait_upper_minutes"], result["point_wait_minutes"])
        self.assertEqual(ticket.estimates.latest("created_at").calculation_version, "aaw_v1")

    def test_payment_legal_transitions_and_history(self):
        appointment = book_appointment(self.request_for(self.patient_user), self.patient.pk, self.schedule.pk, self.department.pk, self.start_at)
        paid = change_payment(self.request_for(self.reception_user), appointment.pk, PaymentRecord.State.PAID_ON_SITE, reference="CASH-TEST")
        self.assertEqual(paid.state, PaymentRecord.State.PAID_ON_SITE)
        refunded = change_payment(
            self.request_for(self.reception_user),
            appointment.pk,
            PaymentRecord.State.REFUNDED,
            reason="Duplicate collection",
            reference="RFND-0001",
        )
        self.assertEqual(refunded.state, PaymentRecord.State.REFUNDED)
        self.assertEqual(PaymentHistory.objects.filter(payment=paid).count(), 2)
        with self.assertRaises(Conflict):
            change_payment(self.request_for(self.reception_user), appointment.pk, PaymentRecord.State.PAID_ON_SITE)

    def test_append_only_queue_event_rejects_changes_and_delete(self):
        ticket = self.make_waiting_ticket()
        event = ticket.events.get()
        event.reason = "changed"
        with self.assertRaises(DjangoValidationError):
            event.save()
        with self.assertRaises(DjangoValidationError):
            event.delete()
