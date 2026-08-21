import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.models import RoleAssignment, User
from directory.models import Chamber, Department, DoctorProfile, Hospital, Location, PatientProfile, PrivacyNoticeVersion
from operations.models import Schedule


class HospitalTestCase(TestCase):
    password = "StrongPatient!2026"

    def setUp(self):
        super().setUp()
        cache.clear()
        self.hospital = Hospital.objects.create(
            display_name="Test Community Hospital",
            short_name="TCH",
            timezone="Asia/Dhaka",
            currency="BDT",
            email="hospital@example.test",
            phone="+8801700000000",
            address="Synthetic test address",
        )
        self.notice = PrivacyNoticeVersion.objects.create(
            hospital=self.hospital,
            version="test-1",
            title="Test privacy notice",
            content="Synthetic test content.",
            effective_at=timezone.now(),
            is_published=True,
        )
        self.hospital.active_privacy_notice = self.notice
        self.hospital.save(update_fields=["active_privacy_notice", "updated_at"])
        self.department = Department.objects.create(hospital=self.hospital, name="General Medicine")
        self.location = Location.objects.create(hospital=self.hospital, name="Main Building", address="Synthetic test address")
        self.chamber = Chamber.objects.create(location=self.location, name="Room 1")

        self.patient_user = self.create_user("patient@example.test", "patient")
        self.patient = PatientProfile.objects.create(
            hospital=self.hospital,
            user=self.patient_user,
            full_name="Synthetic Patient",
            email=self.patient_user.email,
            phone="+8801800000001",
            date_of_birth=timezone.localdate().replace(year=1990),
            sex="unspecified",
            address="Synthetic patient address",
            is_claimed=True,
        )
        self.doctor_user = self.create_user("doctor@example.test", "doctor", staff=True)
        self.doctor = DoctorProfile.objects.create(
            hospital=self.hospital,
            user=self.doctor_user,
            doctor_code="D001",
            display_name="Dr Synthetic",
            designation="Consultant",
            consultation_fee_minor=75000,
        )
        self.doctor.departments.add(self.department)
        self.reception_user = self.create_user("reception@example.test", "receptionist", staff=True)
        self.admin_user = self.create_user("admin@example.test", "administrator", staff=True)
        self.service_date = timezone.localdate()
        self.schedule = Schedule.objects.create(
            hospital=self.hospital,
            doctor=self.doctor,
            location=self.location,
            chamber=self.chamber,
            weekday=self.service_date.weekday(),
            start_local=time(9, 0),
            end_local=time(12, 0),
            slot_duration_minutes=15,
            capacity_per_slot=1,
            effective_from=timezone.localdate(),
        )
        local_start = datetime.combine(self.service_date, time(9, 0), tzinfo=ZoneInfo("Asia/Dhaka"))
        self.start_at = local_start.astimezone(ZoneInfo("UTC"))
        self.factory = RequestFactory()

    def create_user(self, email, role, staff=False):
        user = User.objects.create_user(
            email,
            self.password,
            display_name=email.split("@")[0].title(),
            email_verified_at=timezone.now(),
            is_staff=staff,
        )
        RoleAssignment.objects.create(user=user, role=role)
        return user

    def request_for(self, user, method="post", path="/test/", data=None):
        request = getattr(self.factory, method)(path, data=data or {}, content_type="application/json")
        request.user = user
        request.request_id = uuid.uuid4()
        return request
