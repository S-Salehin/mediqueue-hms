import threading
import uuid
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import RoleAssignment, User
from core.exceptions import Conflict
from directory.models import Chamber, Department, DoctorProfile, Hospital, Location, MRNSequence, PatientProfile
from operations.models import Appointment, QueueSession, QueueTicket, Schedule
from operations.services import book_appointment, call_next, check_in


class PostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.fixed_now = datetime(2026, 8, 14, 2, 0, tzinfo=ZoneInfo("UTC"))
        self.timezone_now_patcher = patch("django.utils.timezone.now", return_value=self.fixed_now)
        self.timezone_now_patcher.start()
        self.addCleanup(self.timezone_now_patcher.stop)
        self.hospital = Hospital.objects.create(display_name="Concurrency Test Hospital", short_name="CTH", timezone="Asia/Dhaka")
        self.department = Department.objects.create(hospital=self.hospital, name="General Medicine")
        self.location = Location.objects.create(hospital=self.hospital, name="Main", address="Synthetic")
        self.chamber = Chamber.objects.create(location=self.location, name="C1")
        self.doctor_user = self.user("doctor-concurrency@example.test", "doctor")
        self.doctor = DoctorProfile.objects.create(
            hospital=self.hospital, user=self.doctor_user, doctor_code="C001", display_name="Dr Concurrency", designation="Consultant"
        )
        self.doctor.departments.add(self.department)
        self.reception = self.user("reception-concurrency@example.test", "receptionist")
        self.patient_users = [self.user(f"concurrent-patient-{index}@example.test", "patient") for index in range(2)]
        self.patients = [
            PatientProfile.objects.create(
                hospital=self.hospital,
                user=user,
                full_name=f"Concurrent Patient {index}",
                email=user.email,
                phone=f"+88018000010{index:02d}",
                date_of_birth=timezone.localdate().replace(year=1990 + index),
                address="Synthetic",
                is_claimed=True,
            )
            for index, user in enumerate(self.patient_users)
        ]
        self.service_date = timezone.localdate()
        self.schedule = Schedule.objects.create(
            hospital=self.hospital,
            doctor=self.doctor,
            location=self.location,
            chamber=self.chamber,
            weekday=self.service_date.weekday(),
            start_local=time(9),
            end_local=time(10),
            slot_duration_minutes=15,
            capacity_per_slot=1,
            effective_from=timezone.localdate(),
        )
        self.start_at = datetime.combine(self.service_date, time(9), tzinfo=ZoneInfo("Asia/Dhaka")).astimezone(ZoneInfo("UTC"))

    def user(self, email, role):
        user = User.objects.create_user(
            email, "ConcurrencyStrong!2026", display_name=email.split("@")[0], email_verified_at=timezone.now(), is_staff=role != "patient"
        )
        RoleAssignment.objects.create(user=user, role=role)
        return user

    def request(self, user):
        return SimpleNamespace(user=user, request_id=uuid.uuid4())

    def test_two_patients_competing_for_last_capacity_have_one_winner(self):
        barrier = threading.Barrier(3)
        outcomes = []
        lock = threading.Lock()

        def worker(user_id, patient_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                barrier.wait(timeout=10)
                appointment = book_appointment(self.request(user), patient_id, self.schedule.pk, self.department.pk, self.start_at)
                result = ("created", str(appointment.pk))
            except Conflict as exc:
                result = ("conflict", exc.get_codes())
            except Exception as exc:
                result = ("error", f"{exc.__class__.__name__}: {exc}")
            finally:
                connection.close()
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker, args=(user.pk, patient.pk)) for user, patient in zip(self.patient_users, self.patients, strict=True)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=20)
        self.assertEqual(sorted(item[0] for item in outcomes), ["conflict", "created"])
        self.assertEqual(Appointment.objects.filter(schedule=self.schedule, start_at=self.start_at, status=Appointment.Status.CONFIRMED).count(), 1)

    def test_two_staff_call_next_requests_create_one_active_ticket(self):
        first = book_appointment(self.request(self.patient_users[0]), self.patients[0].pk, self.schedule.pk, self.department.pk, self.start_at)
        second = book_appointment(
            self.request(self.patient_users[1]), self.patients[1].pk, self.schedule.pk, self.department.pk, self.start_at + timedelta(minutes=15)
        )
        first_ticket = check_in(self.request(self.reception), first.pk)
        check_in(self.request(self.reception), second.pk)
        barrier = threading.Barrier(3)
        outcomes = []
        lock = threading.Lock()

        def worker():
            close_old_connections()
            try:
                user = User.objects.get(pk=self.doctor_user.pk)
                barrier.wait(timeout=10)
                ticket = call_next(self.request(user), first_ticket.session_id)
                result = ("called", str(ticket.pk))
            except Conflict as exc:
                result = ("conflict", exc.get_codes())
            except Exception as exc:
                result = ("error", f"{exc.__class__.__name__}: {exc}")
            finally:
                connection.close()
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=20)
        self.assertEqual(sorted(item[0] for item in outcomes), ["called", "conflict"])
        self.assertEqual(
            QueueTicket.objects.filter(session_id=first_ticket.session_id, state__in=[QueueTicket.State.CALLED, QueueTicket.State.IN_SERVICE]).count(), 1
        )
        session = QueueSession.objects.get(pk=first_ticket.session_id)
        self.assertIsNotNone(session.active_ticket_id)


class FirstMRNConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_first_mrn_allocation_serializes_sequence_creation(self):
        hospital = Hospital.objects.create(
            display_name="First MRN Concurrency Hospital",
            short_name="FMH",
            timezone="Asia/Dhaka",
        )
        barrier = threading.Barrier(3)
        results = []
        lock = threading.Lock()

        def worker(index):
            close_old_connections()
            try:
                local_hospital = Hospital.objects.get(pk=hospital.pk)
                barrier.wait(timeout=10)
                patient = PatientProfile.objects.create(
                    hospital=local_hospital,
                    full_name=f"First MRN Patient {index}",
                    phone=f"+8801800002{index:03d}",
                    date_of_birth=timezone.localdate().replace(year=1990),
                    address="Synthetic",
                )
                result = ("created", patient.mrn)
            except Exception as exc:
                result = ("error", f"{exc.__class__.__name__}: {exc}")
            finally:
                connection.close()
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=20)
        self.assertEqual(sorted(item[0] for item in results), ["created", "created"])
        self.assertEqual(sorted(item[1] for item in results), ["MRN-FMH-0000001", "MRN-FMH-0000002"])
        self.assertEqual(MRNSequence.objects.get(hospital=hospital).next_value, 3)
