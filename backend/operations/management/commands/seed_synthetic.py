import random
import uuid
from datetime import time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import RoleAssignment, StaffMFADevice, User
from communications.models import NotificationPreference
from directory.models import Chamber, ConsentRecord, Department, DoctorProfile, Hospital, Location, PatientProfile, PrivacyNoticeVersion
from operations.models import Appointment, AppointmentHistory, PaymentRecord, Schedule

DEPARTMENTS = [
    "Cardiology",
    "Dermatology",
    "General Medicine",
    "Neurology",
    "Orthopaedics",
    "Ophthalmology",
    "Paediatrics",
    "Respiratory Medicine",
    "Urology",
    "Women's Health",
]


class Command(BaseCommand):
    help = "Create a deterministic, unmistakably synthetic development dataset."

    def add_arguments(self, parser):
        parser.add_argument("--doctors", type=int, default=30)
        parser.add_argument("--appointments", type=int, default=500)

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Synthetic seed is disabled when DJANGO_DEBUG is false.")
        if Hospital.objects.exists():
            raise CommandError("Data already exist. Use a new isolated development database.")
        if not 1 <= options["doctors"] <= 30:
            raise CommandError("doctors must be between 1 and the pilot limit of 30.")
        if not 1 <= options["appointments"] <= 500:
            raise CommandError("appointments must be between 1 and the daily pilot limit of 500.")
        random.seed(1064)
        hospital = Hospital.objects.create(
            display_name="Shapla Community Hospital Demo",
            short_name="SCH",
            email="contact@example.test",
            phone="+8801700000000",
            address="Synthetic Road, Dhaka",
        )
        notice = PrivacyNoticeVersion.objects.create(
            hospital=hospital,
            version="demo-1",
            title="Synthetic demonstration privacy notice",
            content="This environment contains synthetic demonstration records only.",
            effective_at=timezone.now(),
            is_published=True,
        )
        hospital.active_privacy_notice = notice
        hospital.save(update_fields=["active_privacy_notice", "updated_at"])
        departments = [Department.objects.create(hospital=hospital, name=name, display_order=index) for index, name in enumerate(DEPARTMENTS)]
        location = Location.objects.create(hospital=hospital, name="Main Building", code="MAIN", address="Synthetic Road, Dhaka", phone="+8801700000001")
        chambers = [Chamber.objects.create(location=location, name=f"Chamber {number:02d}") for number in range(1, options["doctors"] + 1)]
        doctors = []
        today_schedules = []
        future_schedules = []
        today = timezone.localdate()
        future_date = today + timedelta(days=1)
        for index in range(1, options["doctors"] + 1):
            user = User.objects.create_user(
                f"doctor{index:02d}@example.test",
                "SyntheticOnly!2026",
                display_name=f"Dr Synthetic {index:02d}",
                email_verified_at=timezone.now(),
                is_staff=True,
            )
            RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.DOCTOR)
            department = departments[(index - 1) % len(departments)]
            doctor = DoctorProfile.objects.create(
                hospital=hospital,
                user=user,
                doctor_code=f"D{index:03d}",
                display_name=user.display_name,
                designation=f"Consultant, {department.name}",
                biography="Synthetic profile for demonstration and testing.",
                consultation_fee_minor=50000 + index * 1000,
            )
            doctor.departments.add(department)
            doctors.append(doctor)
            today_schedules.append(
                Schedule.objects.create(
                    hospital=hospital,
                    doctor=doctor,
                    location=location,
                    chamber=chambers[index - 1],
                    weekday=today.weekday(),
                    start_local=time(8, 0),
                    end_local=time(18, 0),
                    slot_duration_minutes=20,
                    capacity_per_slot=2,
                    effective_from=today,
                )
            )
            future_schedules.append(
                Schedule.objects.create(
                    hospital=hospital,
                    doctor=doctor,
                    location=location,
                    chamber=chambers[index - 1],
                    weekday=future_date.weekday(),
                    start_local=time(8, 0),
                    end_local=time(18, 0),
                    slot_duration_minutes=20,
                    capacity_per_slot=2,
                    effective_from=today,
                )
            )
        patients = []
        for index in range(1, max(options["appointments"], 100) + 1):
            patient = PatientProfile.objects.create(
                hospital=hospital,
                full_name=f"Synthetic Patient {index:04d}",
                email=f"patient{index:04d}@example.test",
                phone=f"+88018{index:08d}",
                date_of_birth=timezone.localdate().replace(year=1980 + index % 35),
                sex=["female", "male", "other", "unspecified"][index % 4],
                address=f"Synthetic Address {index}, Dhaka",
                registration_source=PatientProfile.RegistrationSource.RECEPTION,
            )
            patients.append(patient)
        patient_user = User.objects.create_user(
            "patient.demo@example.test", "SyntheticOnly!2026", display_name=patients[0].full_name, email_verified_at=timezone.now()
        )
        RoleAssignment.objects.create(user=patient_user, role=RoleAssignment.Role.PATIENT)
        patients[0].user = patient_user
        patients[0].email = patient_user.email
        patients[0].is_claimed = True
        patients[0].save(update_fields=["user", "email", "is_claimed", "updated_at"])
        staff_accounts = [
            ("reception.demo@example.test", "Synthetic Receptionist", RoleAssignment.Role.RECEPTIONIST, "KRSXG5DSNFXGOIDB"),
            ("admin.demo@example.test", "Synthetic Administrator", RoleAssignment.Role.ADMINISTRATOR, "MFRGGZDFMZTWQ2LK"),
        ]
        staff_by_role = {}
        for email, name, role, secret in staff_accounts:
            user = User.objects.create_user(email, "SyntheticOnly!2026", display_name=name, email_verified_at=timezone.now(), is_staff=True)
            RoleAssignment.objects.create(user=user, role=role)
            staff_by_role[role] = user
            device = StaffMFADevice(user=user, confirmed_at=timezone.now())
            device.set_secret(secret)
            device.save()
        consent_actor = staff_by_role[RoleAssignment.Role.RECEPTIONIST]
        ConsentRecord.objects.bulk_create(
            [
                ConsentRecord(
                    patient=patient,
                    notice_version=notice,
                    purpose="service_and_privacy_notice",
                    decision=True,
                    channel=ConsentRecord.Channel.ASSISTED,
                    actor=consent_actor,
                    request_id=uuid.uuid4(),
                )
                for patient in patients
            ]
        )
        ConsentRecord.objects.create(
            patient=patients[0],
            notice_version=notice,
            purpose="email_notifications",
            decision=True,
            channel=ConsentRecord.Channel.ASSISTED,
            actor=consent_actor,
            request_id=uuid.uuid4(),
        )
        NotificationPreference.objects.create(
            user=patient_user,
            appointment_email=True,
            queue_email=True,
            in_app=True,
        )
        doctor_device = StaffMFADevice(user=doctors[0].user, confirmed_at=timezone.now())
        doctor_device.set_secret("JBSWY3DPEHPK3PXP")
        doctor_device.save()
        zone = __import__("zoneinfo").ZoneInfo(hospital.timezone)
        actor = doctors[0].user
        today_count = min(options["appointments"], options["doctors"])
        for index in range(options["appointments"]):
            is_today = index < today_count
            schedule_pool = today_schedules if is_today else future_schedules
            service_date = today if is_today else future_date
            schedule = schedule_pool[index % len(schedule_pool)]
            pool_index = index if is_today else index - today_count
            slot_index = (pool_index // len(schedule_pool)) % 30
            start_at = timezone.make_aware(__import__("datetime").datetime.combine(service_date, time(8, 0)), zone) + timedelta(minutes=20 * slot_index)
            appointment = Appointment.objects.create(
                hospital=hospital,
                patient=patients[index],
                doctor=schedule.doctor,
                department=schedule.doctor.departments.first(),
                location=location,
                chamber=schedule.chamber,
                schedule=schedule,
                start_at=start_at,
                end_at=start_at + timedelta(minutes=20),
                source=Appointment.Source.RECEPTION,
                booking_actor=actor,
            )
            AppointmentHistory.objects.create(
                appointment=appointment, event="created", actor=actor, new_values={"status": appointment.status}, request_id=appointment.pk
            )
            PaymentRecord.objects.create(appointment=appointment, amount_minor=schedule.doctor.consultation_fee_minor)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(doctors)} doctors, {len(patients)} patients, and {options['appointments']} appointments ({today_count} for today's queue UAT)."
            )
        )
        self.stdout.write("All names, addresses, phone numbers, and example.test emails are synthetic.")
        self.stdout.write("Demo password for all four workspaces: SyntheticOnly!2026")
        self.stdout.write("Patient: patient.demo@example.test")
        self.stdout.write("Doctor: doctor01@example.test, TOTP secret JBSWY3DPEHPK3PXP")
        self.stdout.write("Reception: reception.demo@example.test, TOTP secret KRSXG5DSNFXGOIDB")
        self.stdout.write("Administrator: admin.demo@example.test, TOTP secret MFRGGZDFMZTWQ2LK")
