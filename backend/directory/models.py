import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Q

from core.models import AppendOnlyModel, TimeStampedUUIDModel

phone_validator = RegexValidator(r"^\+[1-9]\d{7,14}$", "Use an E.164 phone number.")


def normalize_space(value):
    return " ".join((value or "").split())


def normalize_identifier(value, label, min_length=1, max_length=12):
    normalized = normalize_space(value).upper()
    if not re.fullmatch(rf"[A-Z0-9]{{{min_length},{max_length}}}", normalized):
        raise ValidationError({label: f"Use {min_length} to {max_length} uppercase ASCII letters or digits."})
    return normalized


class Hospital(TimeStampedUUIDModel):
    display_name = models.CharField(max_length=180)
    short_name = models.CharField(max_length=12)
    tagline = models.CharField(max_length=240, blank=True)
    logo_url = models.CharField(max_length=300, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Dhaka")
    currency = models.CharField(max_length=3, default="BDT")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    address = models.CharField(max_length=500, blank=True)
    operational_settings = models.JSONField(default=dict, blank=True)
    active_privacy_notice = models.ForeignKey("PrivacyNoticeVersion", null=True, blank=True, related_name="active_for_hospitals", on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["is_active"], condition=Q(is_active=True), name="single_active_hospital")]

    def clean(self):
        super().clean()
        if self.timezone != "Asia/Dhaka":
            raise ValidationError({"timezone": "The pilot uses Asia/Dhaka."})
        if (self.currency or "").upper() != "BDT":
            raise ValidationError({"currency": "The pilot records BDT only."})

    def save(self, *args, **kwargs):
        self.display_name = normalize_space(self.display_name)
        self.short_name = normalize_identifier(self.short_name, "short_name", min_length=2)
        self.tagline = normalize_space(self.tagline)
        self.timezone = "Asia/Dhaka"
        self.currency = "BDT"
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class Department(TimeStampedUUIDModel):
    hospital = models.ForeignKey(Hospital, related_name="departments", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [models.UniqueConstraint(fields=["hospital", "name"], name="unique_department_name")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_space(self.name)
        return super().save(*args, **kwargs)


class Location(TimeStampedUUIDModel):
    hospital = models.ForeignKey(Hospital, related_name="locations", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=12, default="MAIN")
    address = models.CharField(max_length=500)
    phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["hospital", "name"], name="unique_location_name"),
            models.UniqueConstraint(fields=["hospital", "code"], name="unique_location_code"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_space(self.name)
        self.code = normalize_identifier(self.code, "code")
        return super().save(*args, **kwargs)


class Chamber(TimeStampedUUIDModel):
    location = models.ForeignKey(Location, related_name="chambers", on_delete=models.PROTECT)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["location", "name"], name="unique_chamber_name")]

    def __str__(self):
        return f"{self.location.name}, {self.name}"


class DoctorProfile(TimeStampedUUIDModel):
    hospital = models.ForeignKey(Hospital, related_name="doctors", on_delete=models.PROTECT)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="doctor_profile", on_delete=models.PROTECT)
    doctor_code = models.CharField(max_length=12)
    display_name = models.CharField(max_length=160)
    designation = models.CharField(max_length=160)
    registration_reference = models.CharField(max_length=100, blank=True)
    departments = models.ManyToManyField(Department, related_name="doctors")
    biography = models.TextField(blank=True)
    consultation_fee_minor = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]
        constraints = [models.UniqueConstraint(fields=["hospital", "doctor_code"], name="unique_doctor_code")]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        self.doctor_code = normalize_identifier(self.doctor_code, "doctor_code")
        self.display_name = normalize_space(self.display_name)
        self.designation = normalize_space(self.designation)
        return super().save(*args, **kwargs)


class MRNSequence(models.Model):
    hospital = models.OneToOneField(Hospital, primary_key=True, related_name="mrn_sequence", on_delete=models.PROTECT)
    next_value = models.PositiveBigIntegerField(default=1)


class PatientProfile(TimeStampedUUIDModel):
    class RegistrationSource(models.TextChoices):
        SELF_SERVICE = "self_service", "Self service"
        RECEPTION = "reception", "Reception"

    class Sex(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        OTHER = "other", "Other"
        UNSPECIFIED = "unspecified", "Prefer not to say"

    hospital = models.ForeignKey(Hospital, related_name="patients", on_delete=models.PROTECT)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="patient_profile", on_delete=models.PROTECT)
    mrn = models.CharField(max_length=32, unique=True, editable=False)
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=16, validators=[phone_validator])
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=16, choices=Sex.choices, default=Sex.UNSPECIFIED)
    address = models.CharField(max_length=500)
    is_claimed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    registration_source = models.CharField(
        max_length=20,
        choices=RegistrationSource.choices,
        default=RegistrationSource.SELF_SERVICE,
    )

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["hospital", "phone"]), models.Index(fields=["hospital", "email"])]

    @classmethod
    def next_mrn(cls, hospital):
        with transaction.atomic():
            Hospital.objects.select_for_update().only("id").get(pk=hospital.pk)
            sequence, _ = MRNSequence.objects.select_for_update().get_or_create(hospital=hospital)
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return f"MRN-{hospital.short_name.upper()[:6]}-{value:07d}"

    def save(self, *args, **kwargs):
        self.full_name = normalize_space(self.full_name)
        self.phone = (self.phone or "").strip()
        if self.email:
            self.email = self.email.strip().lower()
        if not self.mrn:
            self.mrn = self.next_mrn(self.hospital)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mrn} {self.full_name}"


class PatientCorrectionHistory(AppendOnlyModel):
    class Event(models.TextChoices):
        CORRECTED = "corrected", "Corrected"
        DEACTIVATED = "deactivated", "Deactivated"

    patient = models.ForeignKey(PatientProfile, related_name="correction_history", on_delete=models.PROTECT)
    event = models.CharField(max_length=20, choices=Event.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500)
    previous_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    request_id = models.UUIDField(db_index=True)

    class Meta:
        ordering = ["created_at"]


class PrivacyNoticeVersion(AppendOnlyModel):
    hospital = models.ForeignKey(Hospital, related_name="privacy_notices", on_delete=models.PROTECT)
    version = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    content = models.TextField()
    effective_at = models.DateTimeField()
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-effective_at"]
        constraints = [models.UniqueConstraint(fields=["hospital", "version"], name="unique_privacy_notice_version")]


class ConsentRecord(AppendOnlyModel):
    class Channel(models.TextChoices):
        SELF_SERVICE = "self_service", "Self service"
        ASSISTED = "assisted", "Assisted"

    patient = models.ForeignKey(PatientProfile, related_name="consents", on_delete=models.PROTECT)
    notice_version = models.ForeignKey(PrivacyNoticeVersion, related_name="consents", on_delete=models.PROTECT)
    purpose = models.CharField(max_length=100)
    decision = models.BooleanField()
    channel = models.CharField(max_length=20, choices=Channel.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    request_id = models.UUIDField(db_index=True)

    def clean(self):
        if self.patient.hospital_id != self.notice_version.hospital_id:
            raise ValidationError("Patient and privacy notice must belong to the same hospital.")
