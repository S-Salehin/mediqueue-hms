import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from rest_framework import serializers

from accounts.serializers import StrictSerializer
from core.exceptions import Conflict

from .models import Appointment, PaymentRecord, QueueTicket, Schedule, ScheduleException


class ScheduleSerializer(serializers.ModelSerializer):
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)
    doctor_display_name = serializers.CharField(source="doctor.display_name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    chamber_name = serializers.CharField(source="chamber.name", read_only=True)
    department_names = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = (
            "id",
            "hospital",
            "doctor",
            "doctor_display_name",
            "department_names",
            "location",
            "location_name",
            "chamber",
            "chamber_name",
            "weekday",
            "weekday_display",
            "start_local",
            "end_local",
            "slot_duration_minutes",
            "capacity_per_slot",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_department_names(self, obj):
        return [department.name for department in obj.doctor.departments.all() if department.is_active]

    def validate(self, attrs):
        instance = self.instance
        hospital = attrs.get("hospital", getattr(instance, "hospital", None))
        doctor = attrs.get("doctor", getattr(instance, "doctor", None))
        location = attrs.get("location", getattr(instance, "location", None))
        chamber = attrs.get("chamber", getattr(instance, "chamber", None))
        if doctor and hospital and doctor.hospital_id != hospital.id:
            raise serializers.ValidationError({"doctor": ["Doctor belongs to another hospital."]})
        if location and hospital and location.hospital_id != hospital.id:
            raise serializers.ValidationError({"location": ["Location belongs to another hospital."]})
        if chamber and location and chamber.location_id != location.id:
            raise serializers.ValidationError({"chamber": ["Chamber belongs to another location."]})
        resulting_active = attrs.get("is_active", getattr(instance, "is_active", True))
        if resulting_active:
            if hospital and not hospital.is_active:
                raise serializers.ValidationError({"hospital": ["An active schedule must belong to the active hospital."]})
            if doctor and (not doctor.is_active or not doctor.user.is_active or not doctor.departments.filter(hospital=hospital, is_active=True).exists()):
                raise serializers.ValidationError({"doctor": ["An active schedule requires an active doctor with an active department."]})
            if location and not location.is_active:
                raise serializers.ValidationError({"location": ["An active schedule requires an active location."]})
            if chamber and (not chamber.is_active or not chamber.location.is_active):
                raise serializers.ValidationError({"chamber": ["An active schedule requires an active chamber and location."]})
        start = attrs.get("start_local", getattr(instance, "start_local", None))
        end = attrs.get("end_local", getattr(instance, "end_local", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_local": ["End time must be after start time."]})
        weekday = attrs.get("weekday", getattr(instance, "weekday", None))
        effective_from = attrs.get("effective_from", getattr(instance, "effective_from", None))
        effective_to = attrs.get("effective_to", getattr(instance, "effective_to", None))
        if effective_from and effective_to and effective_to < effective_from:
            raise serializers.ValidationError({"effective_to": ["The end date cannot be earlier than the start date."]})
        if doctor and chamber and weekday is not None and start and end and effective_from:
            overlaps = Schedule.objects.filter(is_active=True, weekday=weekday, start_local__lt=end, end_local__gt=start).filter(
                Q(doctor=doctor) | Q(chamber=chamber)
            )
            if effective_to:
                overlaps = overlaps.filter(effective_from__lte=effective_to)
            overlaps = overlaps.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
            if instance:
                overlaps = overlaps.exclude(pk=instance.pk)
            if overlaps.exists():
                raise serializers.ValidationError("This schedule overlaps an active doctor or chamber schedule.")
        return attrs


class ScheduleExceptionSerializer(serializers.ModelSerializer):
    actor = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = ScheduleException
        fields = (
            "id",
            "schedule",
            "service_date",
            "kind",
            "start_local",
            "end_local",
            "slot_duration_minutes",
            "capacity_per_slot",
            "reason",
            "actor",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        start = attrs.get("start_local", getattr(self.instance, "start_local", None))
        end = attrs.get("end_local", getattr(self.instance, "end_local", None))
        if kind == ScheduleException.Kind.REPLACEMENT and (not start or not end):
            raise serializers.ValidationError("A replacement requires start and end times.")
        if kind == ScheduleException.Kind.CLOSED and bool(start) != bool(end):
            raise serializers.ValidationError("A partial closure requires both start and end times.")
        if start and end and end <= start:
            raise serializers.ValidationError({"end_local": ["End time must be after start time."]})
        self.ensure_no_invalidated_appointments(attrs)
        return attrs

    def ensure_no_invalidated_appointments(self, attrs=None):
        attrs = attrs or self.validated_data
        instance = self.instance
        schedule = attrs.get("schedule", getattr(instance, "schedule", None))
        service_date = attrs.get("service_date", getattr(instance, "service_date", None))
        if not schedule or not service_date:
            return
        appointments = list(
            Appointment.objects.filter(
                schedule=schedule,
                status=Appointment.Status.CONFIRMED,
                start_at__gte=datetime.combine(service_date, datetime.min.time(), tzinfo=ZoneInfo(schedule.hospital.timezone)).astimezone(ZoneInfo("UTC")),
                start_at__lt=datetime.combine(service_date + timedelta(days=1), datetime.min.time(), tzinfo=ZoneInfo(schedule.hospital.timezone)).astimezone(
                    ZoneInfo("UTC")
                ),
            ).order_by("start_at", "id")
        )
        if not appointments:
            return
        kind = attrs.get("kind", getattr(instance, "kind", None))
        start = attrs.get("start_local", getattr(instance, "start_local", None))
        end = attrs.get("end_local", getattr(instance, "end_local", None))
        invalid_count = 0
        zone = ZoneInfo(schedule.hospital.timezone)
        if kind == ScheduleException.Kind.CLOSED:
            if not start or not end:
                invalid_count = len(appointments)
            else:
                invalid_count = sum(
                    1
                    for appointment in appointments
                    if appointment.start_at.astimezone(zone).time() < end and appointment.end_at.astimezone(zone).time() > start
                )
        else:
            duration = attrs.get("slot_duration_minutes") or getattr(instance, "slot_duration_minutes", None) or schedule.slot_duration_minutes
            capacity = attrs.get("capacity_per_slot") or getattr(instance, "capacity_per_slot", None) or schedule.capacity_per_slot
            cursor = datetime.combine(service_date, start, tzinfo=zone)
            period_end = datetime.combine(service_date, end, tzinfo=zone)
            valid_starts = set()
            while cursor + timedelta(minutes=duration) <= period_end:
                valid_starts.add(cursor.astimezone(ZoneInfo("UTC")))
                cursor += timedelta(minutes=duration)
            counts = {}
            for appointment in appointments:
                if appointment.start_at not in valid_starts:
                    invalid_count += 1
                else:
                    counts[appointment.start_at] = counts.get(appointment.start_at, 0) + 1
            invalid_count += sum(max(0, count - capacity) for count in counts.values())
        if invalid_count:
            raise Conflict(
                f"Resolve {invalid_count} confirmed appointment(s) invalidated by this exception first.",
                code="confirmed_appointments_invalidated",
            )


class BookingSerializer(StrictSerializer):
    patient_id = serializers.UUIDField(required=False)
    schedule_id = serializers.UUIDField()
    department_id = serializers.UUIDField()
    start_at = serializers.DateTimeField()


class RescheduleSerializer(StrictSerializer):
    schedule_id = serializers.UUIDField()
    department_id = serializers.UUIDField()
    start_at = serializers.DateTimeField()
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ReasonSerializer(StrictSerializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    reason_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")


class AppointmentSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    chamber = serializers.SerializerMethodField()
    payment_state = serializers.CharField(source="payment.state", read_only=True)
    payment_amount_minor = serializers.IntegerField(source="payment.amount_minor", read_only=True)
    queue_id = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = (
            "id",
            "patient",
            "doctor",
            "department",
            "location",
            "chamber",
            "schedule",
            "start_at",
            "end_at",
            "source",
            "status",
            "payment_state",
            "payment_amount_minor",
            "queue_id",
            "queue",
            "created_at",
            "updated_at",
        )

    def get_patient(self, obj):
        return {"id": str(obj.patient_id), "mrn": obj.patient.mrn, "full_name": obj.patient.full_name}

    def get_doctor(self, obj):
        return {"id": str(obj.doctor_id), "display_name": obj.doctor.display_name}

    def get_department(self, obj):
        return {"id": str(obj.department_id), "name": obj.department.name}

    def get_location(self, obj):
        return {"id": str(obj.location_id), "name": obj.location.name}

    def get_chamber(self, obj):
        return {"id": str(obj.chamber_id), "name": obj.chamber.name}

    def get_queue_id(self, obj):
        try:
            return str(obj.queue_ticket.session_id)
        except QueueTicket.DoesNotExist:
            return None

    def get_queue(self, obj):
        try:
            ticket = obj.queue_ticket
        except QueueTicket.DoesNotExist:
            return None
        return {"queue_id": str(ticket.session_id), "ticket_id": str(ticket.pk), "token": ticket.token, "state": ticket.state}


class WalkInSerializer(BookingSerializer):
    patient_id = serializers.UUIDField()


class QueueTicketStaffSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()
    appointment_time = serializers.DateTimeField(source="appointment.start_at", read_only=True)

    class Meta:
        model = QueueTicket
        fields = (
            "id",
            "session",
            "appointment",
            "appointment_time",
            "token",
            "token_sequence",
            "patient",
            "state",
            "was_late",
            "late_by_minutes",
            "checked_in_at",
            "effective_waiting_at",
            "called_at",
            "service_started_at",
            "service_ended_at",
            "last_transition_at",
        )

    def get_patient(self, obj):
        patient = obj.appointment.patient
        return {"id": str(patient.pk), "mrn": patient.mrn, "full_name": patient.full_name, "date_of_birth": patient.date_of_birth, "sex": patient.sex}


class PaymentActionSerializer(StrictSerializer):
    state = serializers.ChoiceField(choices=PaymentRecord.State.choices)
    amount_minor = serializers.IntegerField(min_value=0, required=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    def validate_reference(self, value):
        value = " ".join(value.split())
        if any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("The reference contains unsupported characters.")
        return value

    def validate(self, attrs):
        reference = attrs.get("reference", "")
        if attrs["state"] in {PaymentRecord.State.PAID_ON_SITE, PaymentRecord.State.REFUNDED} and not reference:
            raise serializers.ValidationError({"reference": ["Enter the hospital receipt, refund, or correction reference."]})
        compact_digits = re.sub(r"[\s-]", "", reference)
        if compact_digits.isdigit() and 13 <= len(compact_digits) <= 19:
            raise serializers.ValidationError({"reference": ["Do not enter a payment card number."]})
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="state", read_only=True)
    patient = serializers.SerializerMethodField()
    appointment_reference = serializers.UUIDField(source="appointment_id", read_only=True)

    class Meta:
        model = PaymentRecord
        fields = (
            "id",
            "appointment",
            "appointment_reference",
            "patient",
            "amount_minor",
            "currency",
            "state",
            "status",
            "collection_channel",
            "recorded_at",
            "reference",
            "created_at",
            "updated_at",
        )

    def get_patient(self, obj):
        patient = obj.appointment.patient
        return {"id": str(patient.pk), "mrn": patient.mrn, "full_name": patient.full_name}
