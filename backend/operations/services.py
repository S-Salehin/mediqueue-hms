import hashlib
import math
import re
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from communications.services import notify_user
from core.exceptions import Conflict
from core.permissions import active_roles
from core.services import audit
from directory.models import Department, PatientProfile

from .models import (
    Appointment,
    AppointmentHistory,
    PaymentHistory,
    PaymentRecord,
    QueueEstimateRecord,
    QueueEvent,
    QueueSession,
    QueueTicket,
    Schedule,
    ScheduleException,
)


def hospital_zone(hospital):
    try:
        return ZoneInfo(hospital.timezone)
    except Exception as exc:
        raise ValidationError({"hospital": ["The hospital timezone is invalid."]}) from exc


def local_day_bounds(hospital, service_date):
    """Return the UTC half-open range for one hospital-local calendar day."""
    zone = hospital_zone(hospital)
    start = datetime.combine(service_date, datetime.min.time(), tzinfo=zone)
    end = start + timedelta(days=1)
    utc = ZoneInfo("UTC")
    return start.astimezone(utc), end.astimezone(utc)


def _constraint_name(error):
    cause = getattr(error, "__cause__", None)
    diagnostics = getattr(cause, "diag", None)
    return getattr(diagnostics, "constraint_name", "")


def effective_schedule_period(schedule, service_date):
    if not schedule.is_active or service_date.weekday() != schedule.weekday:
        return None
    if service_date < schedule.effective_from or (schedule.effective_to and service_date > schedule.effective_to):
        return None
    exception = schedule.exceptions.filter(service_date=service_date).first()
    if exception and exception.kind == ScheduleException.Kind.CLOSED and not exception.start_local:
        return None
    if exception and exception.kind == ScheduleException.Kind.REPLACEMENT:
        return (
            exception.start_local,
            exception.end_local,
            exception.slot_duration_minutes or schedule.slot_duration_minutes,
            exception.capacity_per_slot or schedule.capacity_per_slot,
            None,
        )
    closed_period = (exception.start_local, exception.end_local) if exception and exception.start_local else None
    return schedule.start_local, schedule.end_local, schedule.slot_duration_minutes, schedule.capacity_per_slot, closed_period


def iter_schedule_slots(schedule, service_date):
    period = effective_schedule_period(schedule, service_date)
    if not period:
        return []
    start_local, end_local, duration, capacity, closed_period = period
    zone = hospital_zone(schedule.hospital)
    cursor = datetime.combine(service_date, start_local, tzinfo=zone)
    period_end = datetime.combine(service_date, end_local, tzinfo=zone)
    duration_delta = timedelta(minutes=duration)
    result = []
    while cursor + duration_delta <= period_end:
        local_end = cursor + duration_delta
        if not closed_period or local_end.time() <= closed_period[0] or cursor.time() >= closed_period[1]:
            result.append((cursor.astimezone(ZoneInfo("UTC")), local_end.astimezone(ZoneInfo("UTC")), capacity))
        cursor = local_end
    return result


def available_slots(doctor, date_from, date_to):
    if date_to < date_from or (date_to - date_from).days > 31:
        raise ValidationError({"date_to": ["The availability window must be between 0 and 31 days."]})
    now = timezone.now()
    if not doctor.is_active or not doctor.hospital.is_active or not doctor.departments.filter(is_active=True).exists():
        return []
    schedules = (
        Schedule.objects.filter(
            doctor=doctor,
            is_active=True,
            hospital__is_active=True,
            location__is_active=True,
            chamber__is_active=True,
            chamber__location__is_active=True,
        )
        .select_related("hospital", "location", "chamber")
        .prefetch_related("exceptions")
    )
    output = []
    current = date_from
    while current <= date_to:
        for schedule in schedules:
            for start_at, end_at, capacity in iter_schedule_slots(schedule, current):
                if start_at <= now:
                    continue
                used = Appointment.objects.filter(schedule=schedule, start_at=start_at, status=Appointment.Status.CONFIRMED).count()
                if used >= capacity:
                    continue
                zone = hospital_zone(schedule.hospital)
                output.append(
                    {
                        "schedule_id": str(schedule.pk),
                        "start_at": start_at,
                        "end_at": end_at,
                        "display_start": start_at.astimezone(zone).isoformat(),
                        "display_end": end_at.astimezone(zone).isoformat(),
                        "available_capacity": capacity - used,
                        "location": {"id": str(schedule.location_id), "name": schedule.location.name},
                        "chamber": {"id": str(schedule.chamber_id), "name": schedule.chamber.name},
                    }
                )
        current += timedelta(days=1)
    return sorted(output, key=lambda item: item["start_at"])


def validate_slot(schedule, start_at, exclude_appointment=None):
    if (
        not schedule.is_active
        or not schedule.hospital.is_active
        or not schedule.doctor.is_active
        or not schedule.doctor.user.is_active
        or not schedule.location.is_active
        or not schedule.chamber.is_active
        or not schedule.doctor.departments.filter(hospital=schedule.hospital, is_active=True).exists()
    ):
        raise Conflict("The selected schedule is not active.", code="schedule_inactive")
    if timezone.is_naive(start_at):
        raise ValidationError({"start_at": ["A timezone offset is required."]})
    start_at = start_at.astimezone(ZoneInfo("UTC"))
    if start_at <= timezone.now():
        raise Conflict("Past appointment slots cannot be booked.", code="slot_in_past")
    local_date = start_at.astimezone(hospital_zone(schedule.hospital)).date()
    match = next((slot for slot in iter_schedule_slots(schedule, local_date) if slot[0] == start_at), None)
    if not match:
        raise Conflict("The selected time is not an active schedule slot.", code="slot_unavailable")
    _, end_at, capacity = match
    used = Appointment.objects.filter(schedule=schedule, start_at=start_at, status=Appointment.Status.CONFIRMED)
    if exclude_appointment:
        used = used.exclude(pk=exclude_appointment.pk)
    if used.count() >= capacity:
        raise Conflict("The selected appointment slot is full.", code="slot_full")
    return start_at, end_at


def _appointment_values(appointment):
    return {
        "schedule_id": str(appointment.schedule_id),
        "start_at": appointment.start_at.isoformat(),
        "end_at": appointment.end_at.isoformat(),
        "status": appointment.status,
    }


def _ensure_booking_access(request, patient):
    roles = active_roles(request.user)
    if "patient" in roles and not roles & {"receptionist", "administrator"}:
        if patient.user_id != request.user.pk:
            raise PermissionDenied("You may book only your own appointment.")
    elif not roles & {"receptionist", "administrator"}:
        raise PermissionDenied("This role cannot book appointments.")


@transaction.atomic
def book_appointment(request, patient_id, schedule_id, department_id, start_at, source=None):
    patient = PatientProfile.objects.select_related("user", "hospital").filter(pk=patient_id, is_active=True).first()
    if not patient:
        raise ValidationError({"patient_id": ["An active patient was not found."]})
    _ensure_booking_access(request, patient)
    schedule = Schedule.objects.select_for_update().select_related("hospital", "doctor", "location", "chamber").filter(pk=schedule_id, is_active=True).first()
    if not schedule or not schedule.doctor.is_active or not schedule.location.is_active or not schedule.chamber.is_active:
        raise Conflict("The selected schedule is not active.", code="schedule_inactive")
    if schedule.hospital_id != patient.hospital_id:
        raise ValidationError({"patient_id": ["Patient and schedule must belong to the same hospital."]})
    department = Department.objects.filter(pk=department_id, hospital=schedule.hospital, is_active=True, doctors=schedule.doctor).first()
    if not department:
        raise ValidationError({"department_id": ["The doctor is not active in this department."]})
    start_at, end_at = validate_slot(schedule, start_at)
    roles = active_roles(request.user)
    appointment_source = source or (
        Appointment.Source.PATIENT if "patient" in roles and not roles & {"receptionist", "administrator"} else Appointment.Source.RECEPTION
    )
    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                hospital=schedule.hospital,
                patient=patient,
                doctor=schedule.doctor,
                department=department,
                location=schedule.location,
                chamber=schedule.chamber,
                schedule=schedule,
                start_at=start_at,
                end_at=end_at,
                source=appointment_source,
                booking_actor=request.user,
            )
    except IntegrityError as exc:
        if _constraint_name(exc) == "unique_patient_confirmed_start":
            raise Conflict(
                "This patient already has a confirmed appointment at the selected time.",
                code="duplicate_appointment",
            ) from exc
        raise
    AppointmentHistory.objects.create(
        appointment=appointment,
        event="created",
        actor=request.user,
        new_values=_appointment_values(appointment),
        request_id=request.request_id,
    )
    PaymentRecord.objects.create(
        appointment=appointment,
        amount_minor=schedule.doctor.consultation_fee_minor,
        currency=schedule.hospital.currency,
    )
    audit(request, "appointment.created", appointment, "create", _appointment_values(appointment))
    if patient.user_id:
        notify_user(
            patient.user,
            "appointment",
            "Appointment confirmed",
            "Your appointment is confirmed. Sign in to review the details.",
            appointment.pk,
            "appointment_booked",
            {"url": f"/patient/appointments/{appointment.pk}"},
        )
    return appointment


@transaction.atomic
def reschedule_appointment(request, appointment_id, schedule_id, department_id, start_at, reason=""):
    appointment = Appointment.objects.select_for_update().select_related("patient", "schedule").filter(pk=appointment_id).first()
    if not appointment:
        raise ValidationError({"appointment_id": ["Appointment not found."]})
    _ensure_booking_access(request, appointment.patient)
    if appointment.status != Appointment.Status.CONFIRMED:
        raise Conflict("Only a confirmed appointment can be rescheduled.", code="appointment_terminal")
    if hasattr(appointment, "queue_ticket"):
        raise Conflict("A checked-in appointment cannot be rescheduled.", code="already_checked_in")
    roles = active_roles(request.user)
    if "patient" in roles and not roles & {"receptionist", "administrator"}:
        cutoff_minutes = int(appointment.hospital.operational_settings.get("patient_cancellation_cutoff_minutes", 0))
        if timezone.now() >= appointment.start_at - timedelta(minutes=cutoff_minutes):
            raise Conflict(
                "Online rescheduling is closed for this appointment. Contact reception.",
                code="patient_reschedule_closed",
            )
    schedules = {
        str(item.pk): item
        for item in Schedule.objects.select_for_update()
        .select_related("hospital", "doctor", "location", "chamber")
        .filter(pk__in=[appointment.schedule_id, schedule_id])
        .order_by("pk")
    }
    target = schedules.get(str(schedule_id))
    if not target or not target.is_active:
        raise Conflict("The selected schedule is not active.", code="schedule_inactive")
    if target.hospital_id != appointment.hospital_id:
        raise ValidationError({"schedule_id": ["The schedule belongs to another hospital."]})
    department = Department.objects.filter(pk=department_id, hospital=target.hospital, is_active=True, doctors=target.doctor).first()
    if not department:
        raise ValidationError({"department_id": ["The doctor is not active in this department."]})
    start_at, end_at = validate_slot(target, start_at, exclude_appointment=appointment)
    payment = PaymentRecord.objects.select_for_update().get(appointment=appointment)
    target_fee = target.doctor.consultation_fee_minor
    if payment.amount_minor != target_fee and payment.state != PaymentRecord.State.UNPAID:
        raise Conflict(
            "Correct the existing payment before changing to a doctor with a different fee.",
            code="payment_correction_required",
        )
    previous = _appointment_values(appointment)
    appointment.schedule = target
    appointment.doctor = target.doctor
    appointment.department = department
    appointment.location = target.location
    appointment.chamber = target.chamber
    appointment.start_at = start_at
    appointment.end_at = end_at
    try:
        with transaction.atomic():
            appointment.save()
    except IntegrityError as exc:
        if _constraint_name(exc) == "unique_patient_confirmed_start":
            raise Conflict(
                "This patient already has a confirmed appointment at the selected time.",
                code="duplicate_appointment",
            ) from exc
        raise
    current = _appointment_values(appointment)
    AppointmentHistory.objects.create(
        appointment=appointment,
        event="rescheduled",
        actor=request.user,
        reason=reason,
        previous_values=previous,
        new_values=current,
        request_id=request.request_id,
    )
    audit(request, "appointment.rescheduled", appointment, "reschedule", {"previous": previous, "new": current}, reason)
    if payment.amount_minor != target_fee:
        previous_amount = payment.amount_minor
        payment.amount_minor = target_fee
        payment.currency = "BDT"
        payment.save(update_fields=["amount_minor", "currency", "updated_at"])
        PaymentHistory.objects.create(
            payment=payment,
            actor=request.user,
            reason=reason or "Fee updated with the rescheduled appointment",
            previous_state=payment.state,
            new_state=payment.state,
            previous_amount_minor=previous_amount,
            new_amount_minor=target_fee,
            previous_reference=payment.reference,
            new_reference=payment.reference,
            previous_collection_channel=payment.collection_channel,
            new_collection_channel=payment.collection_channel,
            request_id=request.request_id,
        )
        audit(
            request,
            "payment.fee_updated_after_reschedule",
            payment,
            "correct",
            {"previous_amount_minor": previous_amount, "new_amount_minor": target_fee},
            reason,
        )
    if appointment.patient.user_id:
        notify_user(
            appointment.patient.user,
            "appointment",
            "Appointment updated",
            "Your appointment time was updated. Sign in to review it.",
            appointment.pk,
            "appointment_changed",
            {"url": f"/patient/appointments/{appointment.pk}"},
        )
    return appointment


@transaction.atomic
def cancel_appointment(request, appointment_id, reason=""):
    appointment = Appointment.objects.select_for_update().select_related("patient").filter(pk=appointment_id).first()
    if not appointment:
        raise ValidationError({"appointment_id": ["Appointment not found."]})
    _ensure_booking_access(request, appointment.patient)
    roles = active_roles(request.user)
    if roles & {"receptionist", "administrator"} and not reason.strip():
        raise ValidationError({"reason": ["A concise operational reason is required for staff cancellation."]})
    if "patient" in roles and not roles & {"receptionist", "administrator"}:
        cutoff_minutes = int(appointment.hospital.operational_settings.get("patient_cancellation_cutoff_minutes", 0))
        if timezone.now() >= appointment.start_at - timedelta(minutes=cutoff_minutes):
            raise Conflict(
                "Online cancellation is closed for this appointment. Contact reception.",
                code="patient_cancellation_closed",
            )
        reason = reason.strip() or "Cancelled by patient"
    if appointment.status != Appointment.Status.CONFIRMED:
        raise Conflict("Only a confirmed appointment can be cancelled.", code="appointment_terminal")
    if hasattr(appointment, "queue_ticket"):
        raise Conflict("Use the queue cancellation action after check in.", code="already_checked_in")
    previous = _appointment_values(appointment)
    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])
    AppointmentHistory.objects.create(
        appointment=appointment,
        event="cancelled",
        actor=request.user,
        reason=reason,
        previous_values=previous,
        new_values=_appointment_values(appointment),
        request_id=request.request_id,
    )
    audit(request, "appointment.cancelled", appointment, "cancel", {"previous_status": "confirmed", "new_status": "cancelled"}, reason)
    if appointment.patient.user_id:
        notify_user(
            appointment.patient.user,
            "appointment",
            "Appointment cancelled",
            "Your appointment was cancelled. Sign in to review the details.",
            appointment.pk,
            "appointment_changed",
            {"url": f"/patient/appointments/{appointment.pk}"},
        )
    return appointment


def _actor_role(request):
    roles = active_roles(request.user)
    for role in ("doctor", "receptionist", "administrator", "patient"):
        if role in roles:
            return role
    return ""


def _record_queue_event(request, session, ticket, previous, new, reason="", reason_code="", followed_fifo=True):
    before = session.revision
    session.revision = before + 1
    session.last_material_event_at = timezone.now()
    session.save(update_fields=["revision", "last_material_event_at", "active_ticket", "updated_at"])
    return QueueEvent.objects.create(
        session=session,
        ticket=ticket,
        actor=request.user,
        actor_role=_actor_role(request),
        previous_state=previous,
        new_state=new,
        reason=reason,
        reason_code=reason_code,
        request_id=request.request_id,
        revision_before=before,
        revision_after=session.revision,
        ordering_facts={
            "token": ticket.token,
            "token_sequence": ticket.token_sequence,
            "checked_in_at": ticket.checked_in_at.isoformat(),
            "effective_waiting_at": ticket.effective_waiting_at.isoformat(),
        },
        followed_fifo=followed_fifo,
    )


@transaction.atomic
def check_in(request, appointment_id):
    appointment = (
        Appointment.objects.select_for_update().select_related("doctor", "location", "chamber", "hospital", "patient").filter(pk=appointment_id).first()
    )
    if not appointment:
        raise ValidationError({"appointment_id": ["Appointment not found."]})
    if appointment.status != Appointment.Status.CONFIRMED:
        raise Conflict("Only a confirmed appointment can be checked in.", code="appointment_terminal")
    if QueueTicket.objects.filter(appointment=appointment).exists():
        raise Conflict("This appointment is already checked in.", code="duplicate_check_in")
    now = timezone.now()
    zone = hospital_zone(appointment.hospital)
    service_date = appointment.start_at.astimezone(zone).date()
    if service_date != timezone.localdate(now, zone):
        raise Conflict("Check in is available only on the appointment's local service date.", code="check_in_wrong_date")
    try:
        session, _ = QueueSession.objects.get_or_create(
            doctor=appointment.doctor,
            location=appointment.location,
            chamber=appointment.chamber,
            service_date=service_date,
        )
    except IntegrityError:
        session = QueueSession.objects.get(doctor=appointment.doctor, location=appointment.location, chamber=appointment.chamber, service_date=service_date)
    session = QueueSession.objects.select_for_update().get(pk=session.pk)
    if session.state != QueueSession.State.OPEN:
        raise Conflict("The queue session is not open.", code="queue_not_open")
    if session.tickets.filter(
        appointment__patient=appointment.patient,
        state__in=[
            QueueTicket.State.WAITING,
            QueueTicket.State.CALLED,
            QueueTicket.State.IN_SERVICE,
            QueueTicket.State.DEFERRED,
        ],
    ).exists():
        raise Conflict("This patient already has an active ticket in this queue.", code="active_patient_ticket")
    late_threshold = int(appointment.hospital.operational_settings.get("late_arrival_minutes", 15))
    raw_late_minutes = max(0, int((now - appointment.start_at).total_seconds() // 60))
    was_late = raw_late_minutes > late_threshold
    sequence = session.next_token_sequence
    session.next_token_sequence += 1
    session.save(update_fields=["next_token_sequence", "updated_at"])
    prefix = "".join(char for char in appointment.doctor.doctor_code.upper() if char.isalnum())[:4] or "Q"
    ticket = QueueTicket.objects.create(
        appointment=appointment,
        session=session,
        token=f"{prefix}-{sequence:03d}",
        token_sequence=sequence,
        checked_in_at=now,
        effective_waiting_at=now,
        last_transition_at=now,
        was_late=was_late,
        late_by_minutes=raw_late_minutes if was_late else 0,
    )
    _record_queue_event(request, session, ticket, "", QueueTicket.State.WAITING)
    calculate_estimate(ticket, now=now, persist=True)
    audit(
        request,
        "queue.checked_in",
        ticket,
        "check_in",
        {"appointment_id": str(appointment.pk), "token": ticket.token, "was_late": was_late, "late_by_minutes": ticket.late_by_minutes},
    )
    if appointment.patient.user_id:
        notify_user(
            appointment.patient.user,
            "queue",
            "Queue check in complete",
            "Your final queue token is ready. Sign in to review it.",
            ticket.pk,
            "queue_update",
            {"url": f"/patient/queue/{ticket.session_id}"},
        )
    return ticket


@transaction.atomic
def call_next(request, session_id):
    session = QueueSession.objects.select_for_update().filter(pk=session_id).first()
    if not session:
        raise ValidationError({"queue_id": ["Queue session not found."]})
    if session.state != QueueSession.State.OPEN:
        raise Conflict("The queue session is not open.", code="queue_not_open")
    if session.active_ticket_id:
        raise Conflict("Finish the active queue ticket before calling another.", code="active_ticket_exists")
    ticket = session.tickets.select_for_update().filter(state=QueueTicket.State.WAITING).order_by("effective_waiting_at", "token_sequence", "id").first()
    if not ticket:
        raise Conflict("There is no eligible waiting ticket.", code="queue_empty")
    now = timezone.now()
    previous = ticket.state
    ticket.state = QueueTicket.State.CALLED
    ticket.called_at = now
    ticket.last_transition_at = now
    ticket.save(update_fields=["state", "called_at", "last_transition_at", "updated_at"])
    session.active_ticket = ticket
    _record_queue_event(request, session, ticket, previous, ticket.state)
    audit(request, "queue.ticket_called", ticket, "call", {"token": ticket.token})
    if ticket.appointment.patient.user_id:
        notify_user(
            ticket.appointment.patient.user,
            "queue",
            "Please report to the chamber",
            "Your queue token was called. Follow onsite staff guidance.",
            ticket.pk,
            "queue_update",
            {"url": f"/patient/queue/{ticket.session_id}"},
        )
    return ticket


LEGAL_TRANSITIONS = {
    "start": ({QueueTicket.State.CALLED}, QueueTicket.State.IN_SERVICE, False),
    "defer": ({QueueTicket.State.WAITING, QueueTicket.State.CALLED}, QueueTicket.State.DEFERRED, True),
    "restore": ({QueueTicket.State.DEFERRED}, QueueTicket.State.WAITING, True),
    "complete": ({QueueTicket.State.IN_SERVICE}, QueueTicket.State.COMPLETED, False),
    "no_show": ({QueueTicket.State.WAITING, QueueTicket.State.CALLED, QueueTicket.State.DEFERRED}, QueueTicket.State.NO_SHOW, True),
    "cancel": ({QueueTicket.State.WAITING, QueueTicket.State.CALLED, QueueTicket.State.DEFERRED}, QueueTicket.State.CANCELLED, True),
}


@transaction.atomic
def transition_ticket(request, ticket_id, action, reason="", reason_code=""):
    allowed, target, needs_reason = LEGAL_TRANSITIONS[action]
    if needs_reason and not reason.strip():
        raise ValidationError({"reason": ["A concise operational reason is required."]})
    ticket_reference = QueueTicket.objects.only("session_id").filter(pk=ticket_id).first()
    if not ticket_reference:
        raise ValidationError({"ticket_id": ["Queue ticket not found."]})
    session = QueueSession.objects.select_for_update().get(pk=ticket_reference.session_id)
    ticket = QueueTicket.objects.select_for_update().select_related("appointment__patient", "appointment__schedule").get(pk=ticket_id)
    if ticket.state not in allowed:
        raise Conflict(f"A {ticket.state} ticket cannot perform {action}.", code="illegal_queue_transition")
    if action == "start" and session.active_ticket_id != ticket.pk:
        raise Conflict("Only the active called ticket can start service.", code="not_active_ticket")
    now = timezone.now()
    previous = ticket.state
    ticket.state = target
    ticket.last_transition_at = now
    fields = ["state", "last_transition_at", "updated_at"]
    if action == "start":
        ticket.service_started_at = now
        fields.append("service_started_at")
    elif action == "defer":
        ticket.deferred_at = now
        fields.append("deferred_at")
        if session.active_ticket_id == ticket.pk:
            session.active_ticket = None
    elif action == "restore":
        ticket.restored_at = now
        ticket.effective_waiting_at = now
        fields.extend(["restored_at", "effective_waiting_at"])
    elif action == "complete":
        ticket.service_ended_at = now
        fields.append("service_ended_at")
        session.active_ticket = None
        appointment = Appointment.objects.select_for_update().get(pk=ticket.appointment_id)
        appointment.status = Appointment.Status.COMPLETED
        appointment.save(update_fields=["status", "updated_at"])
        AppointmentHistory.objects.create(
            appointment=appointment, event="completed", actor=request.user, new_values=_appointment_values(appointment), request_id=request.request_id
        )
    elif action == "no_show":
        if session.active_ticket_id == ticket.pk:
            session.active_ticket = None
        appointment = Appointment.objects.select_for_update().get(pk=ticket.appointment_id)
        appointment.status = Appointment.Status.NO_SHOW
        appointment.save(update_fields=["status", "updated_at"])
        AppointmentHistory.objects.create(
            appointment=appointment,
            event="no_show",
            actor=request.user,
            reason=reason,
            new_values=_appointment_values(appointment),
            request_id=request.request_id,
        )
    elif action == "cancel":
        if session.active_ticket_id == ticket.pk:
            session.active_ticket = None
        appointment = Appointment.objects.select_for_update().get(pk=ticket.appointment_id)
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])
        AppointmentHistory.objects.create(
            appointment=appointment,
            event="cancelled_after_check_in",
            actor=request.user,
            reason=reason,
            new_values=_appointment_values(appointment),
            request_id=request.request_id,
        )
    ticket.save(update_fields=fields)
    _record_queue_event(
        request,
        session,
        ticket,
        previous,
        target,
        reason,
        reason_code,
        followed_fifo=action not in {"defer", "restore"},
    )
    audit(request, f"queue.{action}", ticket, action, {"previous_state": previous, "new_state": target}, reason)
    if ticket.appointment.patient.user_id:
        notify_user(
            ticket.appointment.patient.user,
            "queue",
            "Queue status updated",
            "Your hospital queue status changed. Sign in for current guidance.",
            ticket.pk,
            "queue_update",
            {"url": f"/patient/queue/{ticket.session_id}"},
        )
    return ticket


def _decimal_median(values):
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    return ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _completed_samples(doctor):
    tickets = QueueTicket.objects.filter(
        appointment__doctor=doctor,
        state=QueueTicket.State.COMPLETED,
        service_sample_valid=True,
        service_started_at__isnull=False,
        service_ended_at__isnull=False,
    ).order_by("-service_ended_at", "id")[:20]
    samples = []
    ids = []
    for item in tickets:
        seconds = Decimal(str((item.service_ended_at - item.service_started_at).total_seconds()))
        minutes = seconds / Decimal(60)
        if Decimal(1) <= minutes <= Decimal(240):
            samples.append(minutes)
            ids.append(str(item.pk))
    return samples, ids


def calculate_estimate(ticket, now=None, persist=True):
    now = now or timezone.now()
    configured = Decimal(max(5, min(60, ticket.appointment.schedule.slot_duration_minutes)))
    samples, sample_ids = _completed_samples(ticket.appointment.doctor)
    n = len(samples)
    observed_median = _decimal_median(samples) if n else None
    mad = _decimal_median([abs(value - observed_median) for value in samples]) if n >= 5 else None
    spread = Decimal("1.4826") * mad if mad is not None else None
    if n < 5:
        service = configured
        confidence = "low"
    else:
        service = max(Decimal(5), min(Decimal(60), Decimal("0.70") * observed_median + Decimal("0.30") * configured))
        confidence = "medium" if n < 10 else "high"
    active = ticket.session.active_ticket
    active_remaining = Decimal(0)
    elapsed = Decimal(0)
    active_state = active.state if active else ""
    if active and active.pk != ticket.pk:
        if active.state == QueueTicket.State.CALLED:
            active_remaining = service
        elif active.state == QueueTicket.State.IN_SERVICE:
            if not active.service_started_at or active.service_started_at > now:
                return {"available": False, "reason": "inconsistent_active_service", "confidence": confidence}
            elapsed = Decimal(str((now - active.service_started_at).total_seconds())) / Decimal(60)
            active_remaining = max(Decimal(0), service - elapsed)
    waiting_before = 0
    if ticket.state == QueueTicket.State.WAITING:
        waiting_before = (
            ticket.session.tickets.filter(state=QueueTicket.State.WAITING)
            .filter(
                Q(effective_waiting_at__lt=ticket.effective_waiting_at)
                | Q(effective_waiting_at=ticket.effective_waiting_at, token_sequence__lt=ticket.token_sequence)
                | Q(effective_waiting_at=ticket.effective_waiting_at, token_sequence=ticket.token_sequence, id__lt=ticket.id)
            )
            .count()
        )
    active_count = 1 if active and active.pk != ticket.pk and active.state in {QueueTicket.State.CALLED, QueueTicket.State.IN_SERVICE} else 0
    people_ahead = waiting_before + active_count
    if ticket.state == QueueTicket.State.CALLED:
        point = Decimal(0)
    elif ticket.state != QueueTicket.State.WAITING:
        return {"available": False, "reason": f"state_{ticket.state}", "confidence": confidence, "people_ahead": people_ahead}
    else:
        point = active_remaining + Decimal(waiting_before) * service
    point_rounded = int(point.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    q = Decimal(0) if point == 0 else Decimal(waiting_before) + (active_remaining / service)
    if point == 0:
        uncertainty = Decimal(5)
        lower, upper = 0, 5
    elif n >= 5:
        uncertainty = max(Decimal(5), spread * Decimal(str(math.sqrt(float(max(q, Decimal(1)))))))
        lower = int(max(Decimal(0), point - uncertainty).to_integral_value(rounding=ROUND_FLOOR))
        upper = int((point + uncertainty).to_integral_value(rounding=ROUND_CEILING))
    else:
        uncertainty = max(Decimal(10), Decimal("0.50") * point, Decimal("0.50") * configured * Decimal(str(math.sqrt(float(max(q, Decimal(1)))))))
        lower = int(max(Decimal(0), point - uncertainty).to_integral_value(rounding=ROUND_FLOOR))
        upper = int((point + uncertainty).to_integral_value(rounding=ROUND_CEILING))
    safety_buffer = {"low": 20, "medium": 15, "high": 10}[confidence]
    return_by = now + timedelta(minutes=max(0, lower - safety_buffer))
    if return_by <= now + timedelta(minutes=5):
        window_start, window_end = now, now + timedelta(minutes=5)
    else:
        window_start, window_end = return_by - timedelta(minutes=5), return_by
    sample_digest = hashlib.sha256("\n".join(sample_ids).encode()).hexdigest()
    if persist:
        QueueEstimateRecord.objects.create(
            session=ticket.session,
            ticket=ticket,
            sample_digest=sample_digest,
            sample_count=n,
            configured_duration=configured,
            observed_median=observed_median,
            observed_mad=mad,
            observed_spread=spread,
            service_estimate=service,
            active_state=active_state,
            elapsed_minutes=elapsed,
            active_remaining_minutes=active_remaining,
            people_ahead=people_ahead,
            point_wait_minutes=point_rounded,
            uncertainty_minutes=uncertainty,
            wait_lower_minutes=lower,
            wait_upper_minutes=upper,
            confidence=confidence,
            safety_buffer_minutes=safety_buffer,
            return_window_start=window_start,
            return_window_end=window_end,
            queue_revision=ticket.session.revision,
        )
    return {
        "available": True,
        "people_ahead": people_ahead,
        "point_wait_minutes": point_rounded,
        "wait_lower_minutes": lower,
        "wait_upper_minutes": upper,
        "return_window_start": window_start,
        "return_window_end": window_end,
        "confidence": confidence,
        "sample_count": n,
        "sample_count_band": "0-4" if n < 5 else ("5-9" if n < 10 else "10-20"),
        "calculation_version": "aaw_v1",
        "calculated_at": now,
    }


PAYMENT_TRANSITIONS = {
    PaymentRecord.State.UNPAID: {PaymentRecord.State.PAID_ON_SITE, PaymentRecord.State.WAIVED},
    PaymentRecord.State.PAID_ON_SITE: {PaymentRecord.State.REFUNDED},
    PaymentRecord.State.WAIVED: {PaymentRecord.State.UNPAID},
    PaymentRecord.State.REFUNDED: set(),
}


@transaction.atomic
def change_payment(request, appointment_id, target_state, reason="", reference="", amount_minor=None):
    payment = PaymentRecord.objects.select_for_update().select_related("appointment").filter(appointment_id=appointment_id).first()
    if not payment:
        raise ValidationError({"appointment_id": ["Payment record not found."]})
    if target_state not in PAYMENT_TRANSITIONS[payment.state]:
        raise Conflict(f"A {payment.state} payment cannot become {target_state}.", code="illegal_payment_transition")
    if target_state in {PaymentRecord.State.PAID_ON_SITE, PaymentRecord.State.WAIVED} and payment.appointment.status not in {
        Appointment.Status.CONFIRMED,
        Appointment.Status.COMPLETED,
    }:
        raise Conflict("Payment cannot be collected or waived for this appointment state.", code="appointment_not_payable")
    if target_state in {PaymentRecord.State.WAIVED, PaymentRecord.State.REFUNDED, PaymentRecord.State.UNPAID} and not reason.strip():
        raise ValidationError({"reason": ["A concise operational reason is required."]})
    if target_state == PaymentRecord.State.UNPAID and payment.appointment.status != Appointment.Status.CONFIRMED:
        raise Conflict("A waiver can be corrected only before appointment completion.", code="payment_correction_closed")
    old_state = payment.state
    old_amount = payment.amount_minor
    old_reference = payment.reference
    old_collection_channel = payment.collection_channel
    if amount_minor is not None:
        payment.amount_minor = amount_minor
    if target_state == PaymentRecord.State.PAID_ON_SITE and payment.amount_minor <= 0:
        raise ValidationError({"amount_minor": ["A paid onsite record must have a positive amount."]})
    reference = " ".join(reference.split())
    if target_state in {PaymentRecord.State.PAID_ON_SITE, PaymentRecord.State.REFUNDED} and not reference:
        raise ValidationError({"reference": ["Enter the hospital receipt, refund, or correction reference."]})
    compact_digits = re.sub(r"[\s-]", "", reference)
    if compact_digits.isdigit() and 13 <= len(compact_digits) <= 19:
        raise ValidationError({"reference": ["Do not enter a payment card number."]})
    if target_state in {PaymentRecord.State.WAIVED, PaymentRecord.State.UNPAID} and reference:
        raise ValidationError({"reference": ["A reference is not used for this payment state."]})
    payment.state = target_state
    payment.collection_channel = "on_site" if target_state == PaymentRecord.State.PAID_ON_SITE else ""
    payment.recorded_by = request.user
    payment.recorded_at = timezone.now()
    payment.reference = reference
    payment.save()
    PaymentHistory.objects.create(
        payment=payment,
        actor=request.user,
        reason=reason,
        previous_state=old_state,
        new_state=target_state,
        previous_amount_minor=old_amount,
        new_amount_minor=payment.amount_minor,
        previous_reference=old_reference,
        new_reference=payment.reference,
        previous_collection_channel=old_collection_channel,
        new_collection_channel=payment.collection_channel,
        request_id=request.request_id,
    )
    audit(
        request,
        "payment.changed",
        payment,
        "transition",
        {"previous_state": old_state, "new_state": target_state, "previous_amount_minor": old_amount, "new_amount_minor": payment.amount_minor},
        reason,
    )
    return payment
