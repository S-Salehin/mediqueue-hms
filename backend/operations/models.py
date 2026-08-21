from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from core.models import AppendOnlyModel, TimeStampedUUIDModel
from directory.models import Chamber, Department, DoctorProfile, Hospital, Location, PatientProfile


class Schedule(TimeStampedUUIDModel):
    hospital = models.ForeignKey(Hospital, related_name="schedules", on_delete=models.PROTECT)
    doctor = models.ForeignKey(DoctorProfile, related_name="schedules", on_delete=models.PROTECT)
    location = models.ForeignKey(Location, related_name="schedules", on_delete=models.PROTECT)
    chamber = models.ForeignKey(Chamber, related_name="schedules", on_delete=models.PROTECT)
    weekday = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])
    start_local = models.TimeField()
    end_local = models.TimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField(validators=[MinValueValidator(5), MaxValueValidator(60)])
    capacity_per_slot = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(20)])
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["doctor", "weekday", "start_local"]
        constraints = [
            models.CheckConstraint(condition=Q(end_local__gt=F("start_local")), name="schedule_end_after_start"),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")), name="schedule_valid_dates"),
        ]

    def clean(self):
        errors = {}
        if self.doctor_id and self.hospital_id and self.doctor.hospital_id != self.hospital_id:
            errors["doctor"] = "Doctor must belong to the selected hospital."
        if self.location_id and self.hospital_id and self.location.hospital_id != self.hospital_id:
            errors["location"] = "Location must belong to the selected hospital."
        if self.chamber_id and self.location_id and self.chamber.location_id != self.location_id:
            errors["chamber"] = "Chamber must belong to the selected location."
        if self.start_local and self.end_local and self.end_local <= self.start_local:
            errors["end_local"] = "End time must be after start time."
        if self.is_active:
            if self.hospital_id and not self.hospital.is_active:
                errors["hospital"] = "An active schedule must belong to the active hospital."
            if self.doctor_id and (
                not self.doctor.is_active
                or not self.doctor.user.is_active
                or not self.doctor.departments.filter(hospital_id=self.hospital_id, is_active=True).exists()
            ):
                errors["doctor"] = "An active schedule requires an active doctor with an active department."
            if self.location_id and not self.location.is_active:
                errors["location"] = "An active schedule requires an active location."
            if self.chamber_id and (not self.chamber.is_active or not self.chamber.location.is_active):
                errors["chamber"] = "An active schedule requires an active chamber and location."
        if errors:
            raise ValidationError(errors)


class ScheduleException(TimeStampedUUIDModel):
    class Kind(models.TextChoices):
        CLOSED = "closed", "Closed"
        REPLACEMENT = "replacement", "Replacement"

    schedule = models.ForeignKey(Schedule, related_name="exceptions", on_delete=models.PROTECT)
    service_date = models.DateField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    start_local = models.TimeField(null=True, blank=True)
    end_local = models.TimeField(null=True, blank=True)
    slot_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(5), MaxValueValidator(60)])
    capacity_per_slot = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(20)])
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["schedule", "service_date"], name="unique_schedule_exception_date")]

    def clean(self):
        if self.kind == self.Kind.REPLACEMENT and (not self.start_local or not self.end_local):
            raise ValidationError("A replacement requires start and end times.")
        if self.start_local and self.end_local and self.end_local <= self.start_local:
            raise ValidationError({"end_local": "End time must be after start time."})


class Appointment(TimeStampedUUIDModel):
    class Source(models.TextChoices):
        PATIENT = "patient", "Patient"
        RECEPTION = "reception", "Reception"
        WALK_IN = "walk_in", "Walk in"

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No show"

    hospital = models.ForeignKey(Hospital, related_name="appointments", on_delete=models.PROTECT)
    patient = models.ForeignKey(PatientProfile, related_name="appointments", on_delete=models.PROTECT)
    doctor = models.ForeignKey(DoctorProfile, related_name="appointments", on_delete=models.PROTECT)
    department = models.ForeignKey(Department, related_name="appointments", on_delete=models.PROTECT)
    location = models.ForeignKey(Location, related_name="appointments", on_delete=models.PROTECT)
    chamber = models.ForeignKey(Chamber, related_name="appointments", on_delete=models.PROTECT)
    schedule = models.ForeignKey(Schedule, related_name="appointments", on_delete=models.PROTECT)
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    source = models.CharField(max_length=16, choices=Source.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    booking_actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="booked_appointments", on_delete=models.PROTECT)

    class Meta:
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["schedule", "start_at", "status"]), models.Index(fields=["patient", "start_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="appointment_end_after_start"),
            models.UniqueConstraint(
                fields=["patient", "start_at"],
                condition=Q(status="confirmed"),
                name="unique_patient_confirmed_start",
            ),
        ]


class AppointmentHistory(AppendOnlyModel):
    appointment = models.ForeignKey(Appointment, related_name="history", on_delete=models.PROTECT)
    event = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    request_id = models.UUIDField(db_index=True)

    class Meta:
        ordering = ["created_at"]


class QueueSession(TimeStampedUUIDModel):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    doctor = models.ForeignKey(DoctorProfile, related_name="queue_sessions", on_delete=models.PROTECT)
    location = models.ForeignKey(Location, related_name="queue_sessions", on_delete=models.PROTECT)
    chamber = models.ForeignKey(Chamber, related_name="queue_sessions", on_delete=models.PROTECT)
    service_date = models.DateField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.OPEN)
    next_token_sequence = models.PositiveIntegerField(default=1)
    revision = models.PositiveBigIntegerField(default=0)
    active_ticket = models.ForeignKey("QueueTicket", null=True, blank=True, related_name="active_for_sessions", on_delete=models.PROTECT)
    last_material_event_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["doctor", "location", "chamber", "service_date"], name="unique_queue_session")]


class QueueTicket(TimeStampedUUIDModel):
    class State(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        IN_SERVICE = "in_service", "In service"
        DEFERRED = "deferred", "Deferred"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    appointment = models.OneToOneField(Appointment, related_name="queue_ticket", on_delete=models.PROTECT)
    session = models.ForeignKey(QueueSession, related_name="tickets", on_delete=models.PROTECT)
    token = models.CharField(max_length=20)
    token_sequence = models.PositiveIntegerField()
    checked_in_at = models.DateTimeField()
    effective_waiting_at = models.DateTimeField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.WAITING)
    called_at = models.DateTimeField(null=True, blank=True)
    service_started_at = models.DateTimeField(null=True, blank=True)
    service_ended_at = models.DateTimeField(null=True, blank=True)
    deferred_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    last_transition_at = models.DateTimeField()
    service_sample_valid = models.BooleanField(default=True)
    was_late = models.BooleanField(default=False)
    late_by_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["effective_waiting_at", "token_sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["session", "token"], name="unique_queue_token"),
            models.UniqueConstraint(fields=["session", "token_sequence"], name="unique_queue_sequence"),
            models.UniqueConstraint(fields=["session"], condition=Q(state__in=["called", "in_service"]), name="one_active_queue_ticket"),
        ]


class QueueEvent(AppendOnlyModel):
    session = models.ForeignKey(QueueSession, related_name="events", on_delete=models.PROTECT)
    ticket = models.ForeignKey(QueueTicket, related_name="events", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_role = models.CharField(max_length=20)
    previous_state = models.CharField(max_length=16, blank=True)
    new_state = models.CharField(max_length=16)
    reason = models.CharField(max_length=500, blank=True)
    reason_code = models.CharField(max_length=40, blank=True)
    request_id = models.UUIDField(db_index=True)
    revision_before = models.PositiveBigIntegerField()
    revision_after = models.PositiveBigIntegerField()
    ordering_facts = models.JSONField(default=dict)
    followed_fifo = models.BooleanField(default=True)

    class Meta:
        ordering = ["created_at"]


class QueueEstimateRecord(AppendOnlyModel):
    session = models.ForeignKey(QueueSession, related_name="estimates", on_delete=models.PROTECT)
    ticket = models.ForeignKey(QueueTicket, related_name="estimates", on_delete=models.PROTECT)
    calculation_version = models.CharField(max_length=20, default="aaw_v1")
    sample_digest = models.CharField(max_length=64)
    sample_count = models.PositiveSmallIntegerField()
    configured_duration = models.DecimalField(max_digits=7, decimal_places=3)
    observed_median = models.DecimalField(max_digits=7, decimal_places=3, null=True)
    observed_mad = models.DecimalField(max_digits=7, decimal_places=3, null=True)
    observed_spread = models.DecimalField(max_digits=8, decimal_places=3, null=True)
    service_estimate = models.DecimalField(max_digits=7, decimal_places=3)
    active_state = models.CharField(max_length=16, blank=True)
    elapsed_minutes = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    active_remaining_minutes = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    people_ahead = models.PositiveIntegerField(default=0)
    point_wait_minutes = models.PositiveIntegerField(null=True)
    uncertainty_minutes = models.DecimalField(max_digits=8, decimal_places=3, null=True)
    wait_lower_minutes = models.PositiveIntegerField(null=True)
    wait_upper_minutes = models.PositiveIntegerField(null=True)
    confidence = models.CharField(max_length=12)
    safety_buffer_minutes = models.PositiveSmallIntegerField()
    return_window_start = models.DateTimeField(null=True)
    return_window_end = models.DateTimeField(null=True)
    queue_revision = models.PositiveBigIntegerField()


class PaymentRecord(TimeStampedUUIDModel):
    class State(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID_ON_SITE = "paid_on_site", "Paid on site"
        WAIVED = "waived", "Waived"
        REFUNDED = "refunded", "Refunded"

    appointment = models.OneToOneField(Appointment, related_name="payment", on_delete=models.PROTECT)
    amount_minor = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="BDT")
    state = models.CharField(max_length=20, choices=State.choices, default=State.UNPAID)
    collection_channel = models.CharField(max_length=30, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        self.currency = "BDT"
        self.reference = " ".join((self.reference or "").split())
        return super().save(*args, **kwargs)


class PaymentHistory(AppendOnlyModel):
    payment = models.ForeignKey(PaymentRecord, related_name="history", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500, blank=True)
    previous_state = models.CharField(max_length=20, blank=True)
    new_state = models.CharField(max_length=20)
    previous_amount_minor = models.PositiveIntegerField(null=True)
    new_amount_minor = models.PositiveIntegerField()
    previous_reference = models.CharField(max_length=100, blank=True)
    new_reference = models.CharField(max_length=100, blank=True)
    previous_collection_channel = models.CharField(max_length=30, blank=True)
    new_collection_channel = models.CharField(max_length=30, blank=True)
    request_id = models.UUIDField(db_index=True)

    class Meta:
        ordering = ["created_at"]
