import hashlib
import json
import uuid
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import Conflict
from core.pagination import BoundedPagination
from core.permissions import IsAdministrator, IsAuthenticatedWithStaffMFA, IsOperationalStaff, IsReceptionOrAdmin, active_roles
from core.services import audit, idempotent, safe_model_projection
from core.throttling import DatabaseScopedRateThrottle
from directory.models import DoctorProfile, Hospital, PatientProfile

from .models import Appointment, PaymentRecord, QueueEstimateRecord, QueueSession, QueueTicket, Schedule, ScheduleException
from .serializers import (
    AppointmentSerializer,
    BookingSerializer,
    PaymentActionSerializer,
    PaymentSerializer,
    QueueTicketStaffSerializer,
    ReasonSerializer,
    RescheduleSerializer,
    ScheduleExceptionSerializer,
    ScheduleSerializer,
    WalkInSerializer,
)
from .services import (
    available_slots,
    book_appointment,
    calculate_estimate,
    call_next,
    cancel_appointment,
    change_payment,
    check_in,
    hospital_zone,
    local_day_bounds,
    reschedule_appointment,
    transition_ticket,
)


def appointment_queryset(request):
    queryset = Appointment.objects.select_related("patient", "doctor", "department", "location", "chamber", "schedule", "payment")
    roles = active_roles(request.user)
    filters = Q(pk__in=[])
    if "patient" in roles:
        filters |= Q(patient__user=request.user)
    if "doctor" in roles:
        filters |= Q(doctor__user=request.user)
    if roles & {"receptionist", "administrator"}:
        filters |= Q()
        return queryset
    return queryset.filter(filters)


def appointment_data(appointment):
    return AppointmentSerializer(
        Appointment.objects.select_related("patient", "doctor", "department", "location", "chamber", "schedule", "payment").get(pk=appointment.pk)
    ).data


class AvailabilityView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "public"

    def get(self, request, doctor_id):
        doctor = DoctorProfile.objects.filter(
            pk=doctor_id,
            is_active=True,
            user__is_active=True,
            hospital__is_active=True,
        ).first()
        if not doctor:
            return Response({"detail": "Doctor not found.", "code": "not_found"}, status=404)
        try:
            date_from = date.fromisoformat(request.query_params.get("date_from", ""))
            date_to = date.fromisoformat(request.query_params.get("date_to", ""))
        except ValueError:
            return Response({"detail": "date_from and date_to must use YYYY-MM-DD.", "code": "invalid_date"}, status=400)
        if date_from < timezone.localdate():
            date_from = timezone.localdate()
        slots = available_slots(doctor, date_from, date_to)
        return Response({"doctor_id": str(doctor.pk), "date_from": date_from, "date_to": date_to, "slots": slots})


class ScheduleAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Schedule.objects.select_related("hospital", "doctor", "location", "chamber").prefetch_related("doctor__departments")
    serializer_class = ScheduleSerializer

    def create(self, request, *args, **kwargs):
        scope = f"configuration.{self.get_serializer_class().__name__}.create"
        return idempotent(
            request,
            scope,
            lambda: viewsets.ModelViewSet.create(self, request, *args, **kwargs),
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if isinstance(instance, Schedule) and instance.is_active and request.data.get("is_active") is False:
            return Response(
                {"detail": "Use the reasoned schedule deactivation action.", "code": "reason_required"},
                status=400,
            )
        scope = f"configuration.{self.get_serializer_class().__name__}.{instance.pk}.update"

        def operation():
            locked = self.filter_queryset(self.get_queryset()).select_for_update().get(pk=instance.pk)
            self.check_object_permissions(request, locked)
            serializer = self.get_serializer(
                locked,
                data=request.data,
                partial=kwargs.get("partial", False),
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            if getattr(locked, "_prefetched_objects_cache", None):
                locked._prefetched_objects_cache = {}
            return Response(serializer.data)

        return idempotent(
            request,
            scope,
            operation,
        )

    def perform_create(self, serializer):
        schedule = serializer.save()
        audit(self.request, "schedule.created", schedule, "create", serializer.validated_data)

    def perform_update(self, serializer):
        if isinstance(serializer.instance, Schedule):
            structural_fields = (
                "hospital",
                "doctor",
                "location",
                "chamber",
                "weekday",
                "start_local",
                "end_local",
                "slot_duration_minutes",
                "effective_from",
                "effective_to",
            )
            structural_changes = [
                field
                for field in structural_fields
                if field in serializer.validated_data
                and serializer.validated_data[field] != getattr(serializer.instance, field)
            ]
            if structural_changes and serializer.instance.appointments.exists():
                raise Conflict(
                    "This schedule has appointments. Deactivate it and create a replacement schedule.",
                    code="schedule_has_appointments",
                )
            requested_capacity = serializer.validated_data.get("capacity_per_slot")
            if requested_capacity is not None and requested_capacity < serializer.instance.capacity_per_slot:
                peak_confirmed = (
                    Appointment.objects.filter(
                        schedule=serializer.instance,
                        status=Appointment.Status.CONFIRMED,
                    )
                    .values("start_at")
                    .annotate(total=Count("id"))
                    .order_by("-total")
                    .values_list("total", flat=True)
                    .first()
                    or 0
                )
                if requested_capacity < peak_confirmed:
                    raise Conflict(
                        "Capacity cannot be lower than the confirmed bookings in an existing slot.",
                        code="capacity_below_confirmed",
                    )
        before = self.audit_projection(serializer.instance)
        schedule = serializer.save()
        audit(
            self.request,
            "schedule.updated",
            schedule,
            "update",
            {"before": before, "after": self.audit_projection(schedule)},
        )

    @staticmethod
    def audit_projection(obj):
        if isinstance(obj, ScheduleException):
            fields = (
                "schedule_id",
                "service_date",
                "kind",
                "start_local",
                "end_local",
                "slot_duration_minutes",
                "capacity_per_slot",
                "reason",
            )
        else:
            fields = (
                "hospital_id",
                "doctor_id",
                "location_id",
                "chamber_id",
                "weekday",
                "start_local",
                "end_local",
                "slot_duration_minutes",
                "capacity_per_slot",
                "effective_from",
                "effective_to",
                "is_active",
            )
        return safe_model_projection(obj, fields)

    def deactivate(self, request, pk=None):
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"detail": "A concise operational reason is required.", "code": "reason_required"}, status=400)

        def operation():
            schedule = Schedule.objects.select_for_update().filter(pk=pk).first()
            if not schedule:
                return {"detail": "Schedule not found.", "code": "not_found"}, 404
            if schedule.is_active:
                before = self.audit_projection(schedule)
                schedule.is_active = False
                schedule.save(update_fields=["is_active", "updated_at"])
                audit(
                    request,
                    "schedule.deactivated",
                    schedule,
                    "deactivate",
                    {"before": before, "after": self.audit_projection(schedule)},
                    reason,
                )
            return ScheduleSerializer(schedule).data, 200

        return idempotent(request, f"configuration.Schedule.{pk}.deactivate", operation)


class ScheduleExceptionAdminViewSet(ScheduleAdminViewSet):
    queryset = ScheduleException.objects.select_related("schedule", "actor")
    serializer_class = ScheduleExceptionSerializer

    def perform_create(self, serializer):
        Schedule.objects.select_for_update().get(pk=serializer.validated_data["schedule"].pk)
        serializer.ensure_no_invalidated_appointments()
        exception = serializer.save()
        audit(self.request, "schedule_exception.created", exception, "create", serializer.validated_data)

    def perform_update(self, serializer):
        Schedule.objects.select_for_update().get(pk=serializer.instance.schedule_id)
        serializer.ensure_no_invalidated_appointments()
        before = self.audit_projection(serializer.instance)
        exception = serializer.save()
        audit(
            self.request,
            "schedule_exception.updated",
            exception,
            "update",
            {"before": before, "after": self.audit_projection(exception)},
        )


class AppointmentListCreateView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def get(self, request):
        queryset = appointment_queryset(request)
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        doctor = request.query_params.get("doctor") or request.query_params.get("doctor_id")
        if doctor:
            queryset = queryset.filter(doctor_id=doctor)
        if request.query_params.get("date"):
            try:
                selected_date = date.fromisoformat(request.query_params["date"])
            except ValueError:
                return Response({"detail": "date must use YYYY-MM-DD.", "code": "invalid_date"}, status=400)
            hospital = Hospital.objects.filter(is_active=True).first()
            if hospital:
                day_start, day_end = local_day_bounds(hospital, selected_date)
                queryset = queryset.filter(hospital=hospital, start_at__gte=day_start, start_at__lt=day_end)
            else:
                queryset = queryset.none()
        query = request.query_params.get("q", "").strip()
        if query and active_roles(request.user) & {"doctor", "receptionist", "administrator"}:
            if len(query) < 2:
                return Response({"detail": "Search text must contain at least two characters.", "code": "invalid_search"}, status=400)
            if len(query) > 160:
                return Response({"detail": "Search text is too long.", "code": "invalid_search"}, status=400)
            search = Q(patient__full_name__icontains=query) | Q(patient__mrn__iexact=query) | Q(patient__phone__iexact=query) | Q(patient__email__iexact=query)
            try:
                search |= Q(pk=uuid.UUID(query))
            except ValueError:
                pass
            queryset = queryset.filter(search)
        queryset = queryset.order_by("-start_at", "-id")
        paginator = BoundedPagination()
        appointments = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(AppointmentSerializer(appointments, many=True).data)

    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data.copy()
        if "patient_id" not in payload:
            patient = PatientProfile.objects.filter(user=request.user, is_active=True).first()
            if not patient:
                return Response({"detail": "A patient profile is required.", "code": "patient_profile_required"}, status=400)
            payload["patient_id"] = patient.pk
        return idempotent(request, "appointment.book", lambda: (appointment_data(book_appointment(request, **payload)), 201))


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def get(self, request, appointment_id):
        appointment = appointment_queryset(request).filter(pk=appointment_id).first()
        if not appointment:
            return Response({"detail": "Appointment not found.", "code": "not_found"}, status=404)
        if active_roles(request.user) & {"doctor", "receptionist", "administrator"}:
            audit(request, "appointment.viewed", appointment, "read", {"staff_access": True})
        return Response(AppointmentSerializer(appointment).data)


class RescheduleView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, appointment_id):
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return idempotent(
            request,
            f"appointment.{appointment_id}.reschedule",
            lambda: (appointment_data(reschedule_appointment(request, appointment_id, **serializer.validated_data)), 200),
        )


class CancelView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, appointment_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return idempotent(
            request,
            f"appointment.{appointment_id}.cancel",
            lambda: (appointment_data(cancel_appointment(request, appointment_id, serializer.validated_data["reason"])), 200),
        )


class CheckInView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, appointment_id):
        return idempotent(request, f"appointment.{appointment_id}.check_in", lambda: (QueueTicketStaffSerializer(check_in(request, appointment_id)).data, 201))


class WalkInView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request):
        serializer = WalkInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            with transaction.atomic():
                appointment = book_appointment(request, source=Appointment.Source.WALK_IN, **serializer.validated_data)
                ticket = check_in(request, appointment.pk)
            return {"appointment": appointment_data(appointment), "ticket": QueueTicketStaffSerializer(ticket).data}, 201

        return idempotent(request, "reception.walk_in", operation)


def can_operate_queue(user, session):
    roles = active_roles(user)
    return bool(roles & {"receptionist", "administrator"} or ("doctor" in roles and session.doctor.user_id == user.pk))


class CallNextView(APIView):
    permission_classes = [IsOperationalStaff]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, queue_id):
        session = QueueSession.objects.filter(pk=queue_id).first()
        if not session or not can_operate_queue(request.user, session):
            return Response({"detail": "Queue not found.", "code": "not_found"}, status=404)
        return idempotent(request, f"queue.{queue_id}.call_next", lambda: (QueueTicketStaffSerializer(call_next(request, queue_id)).data, 200))


class QueueActionView(APIView):
    permission_classes = [IsOperationalStaff]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"
    action = None

    def post(self, request, ticket_id):
        ticket = QueueTicket.objects.select_related("session__doctor").filter(pk=ticket_id).first()
        if not ticket or not can_operate_queue(request.user, ticket.session):
            return Response({"detail": "Queue ticket not found.", "code": "not_found"}, status=404)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return idempotent(
            request,
            f"queue_ticket.{ticket_id}.{self.action}",
            lambda: (QueueTicketStaffSerializer(transition_ticket(request, ticket_id, self.action, **serializer.validated_data)).data, 200),
        )


def action_view(action):
    return type(f"{action.title()}QueueActionView", (QueueActionView,), {"action": action})


class PatientLeaveQueueView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, ticket_id):
        ticket = (
            QueueTicket.objects.select_related("appointment__patient")
            .filter(
                pk=ticket_id,
                appointment__patient__user=request.user,
                appointment__patient__is_active=True,
            )
            .first()
        )
        if not ticket or "patient" not in active_roles(request.user):
            return Response({"detail": "Queue ticket not found.", "code": "not_found"}, status=404)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"].strip()
        if len(reason) < 3:
            raise ValidationError({"reason": ["Enter a reason containing at least three characters."]})
        return idempotent(
            request,
            f"queue_ticket.{ticket_id}.patient_leave",
            lambda: self._leave(request, ticket_id, reason),
        )

    @staticmethod
    def _leave(request, ticket_id, reason):
        ticket = transition_ticket(
            request,
            ticket_id,
            "cancel",
            reason=reason,
            reason_code="patient_left",
        )
        return {
            "ticket_id": str(ticket.pk),
            "queue_id": str(ticket.session_id),
            "token": ticket.token,
            "state": ticket.state,
        }, 200


class QueueSnapshotView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def get(self, request, queue_id):
        session = QueueSession.objects.select_related("doctor", "location", "chamber", "active_ticket").filter(pk=queue_id).first()
        if not session:
            return Response({"detail": "Queue not found.", "code": "not_found"}, status=404)
        roles = active_roles(request.user)
        patient_ticket = None
        if "patient" in roles:
            own_tickets = session.tickets.select_related(
                "appointment__patient",
                "appointment__schedule",
                "appointment__doctor",
            ).filter(appointment__patient__user=request.user)
            patient_ticket = (
                own_tickets.filter(
                    state__in=[
                        QueueTicket.State.WAITING,
                        QueueTicket.State.CALLED,
                        QueueTicket.State.IN_SERVICE,
                        QueueTicket.State.DEFERRED,
                    ]
                )
                .order_by("-checked_in_at", "-id")
                .first()
            )
            if not patient_ticket:
                patient_ticket = own_tickets.order_by("-checked_in_at", "-id").first()
        if patient_ticket:
            snapshot_time = timezone.now().replace(second=0, microsecond=0)
            estimate = calculate_estimate(patient_ticket, now=snapshot_time, persist=False)
            estimate.pop("sample_count", None)
            current_token = session.active_ticket.token if session.active_ticket_id else None
            body = {
                "queue_id": str(session.pk),
                "ticket_id": str(patient_ticket.pk),
                "token": patient_ticket.token,
                "state": patient_ticket.state,
                "doctor": {"id": str(session.doctor_id), "display_name": session.doctor.display_name},
                "location": {"id": str(session.location_id), "name": session.location.name},
                "chamber": {"id": str(session.chamber_id), "name": session.chamber.name},
                "current_served_token": current_token,
                "last_material_event_at": session.last_material_event_at,
                "stale": False,
                "guidance": "Follow onsite staff guidance because queue movement can change.",
                **estimate,
            }
            projection = f"patient:{request.user.pk}:{json.dumps(body, default=str, sort_keys=True)}"
        elif can_operate_queue(request.user, session):
            tickets = session.tickets.select_related("appointment__patient").order_by("effective_waiting_at", "token_sequence")
            body = {
                "queue_id": str(session.pk),
                "state": session.state,
                "revision": session.revision,
                "doctor": {"id": str(session.doctor_id), "display_name": session.doctor.display_name},
                "active_ticket_id": str(session.active_ticket_id) if session.active_ticket_id else None,
                "current_ticket": QueueTicketStaffSerializer(session.active_ticket).data if session.active_ticket_id else None,
                "current": QueueTicketStaffSerializer(session.active_ticket).data if session.active_ticket_id else None,
                "tickets": QueueTicketStaffSerializer(tickets, many=True).data,
                "last_material_event_at": session.last_material_event_at,
            }
            from core.models import AuditEvent

            if not AuditEvent.objects.filter(
                event_type="queue.identity_viewed",
                actor=request.user,
                subject_id=session.pk,
                created_at__gte=timezone.now() - timedelta(hours=1),
            ).exists():
                audit(request, "queue.identity_viewed", session, "read", {"staff_access": True})
            projection = f"staff:{request.user.pk}:{session.revision}:{json.dumps(body, default=str, sort_keys=True)}"
        else:
            return Response({"detail": "Queue not found.", "code": "not_found"}, status=404)
        etag = '"' + hashlib.sha256(projection.encode()).hexdigest() + '"'
        if request.headers.get("If-None-Match") == etag:
            response = Response(status=304)
        else:
            response = Response(body)
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-store"
        return response


class PaymentView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def get(self, request, appointment_id):
        roles = active_roles(request.user)
        queryset = Appointment.objects.select_related("patient", "payment")
        if roles & {"receptionist", "administrator"}:
            pass
        elif "patient" in roles:
            queryset = queryset.filter(patient__user=request.user)
        else:
            queryset = queryset.none()
        appointment = queryset.filter(pk=appointment_id).first()
        if not appointment:
            return Response({"detail": "Appointment not found.", "code": "not_found"}, status=404)
        return Response(PaymentSerializer(appointment.payment).data)


class PaymentActionView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, appointment_id):
        serializer = PaymentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return idempotent(
            request,
            f"appointment.{appointment_id}.payment",
            lambda: (
                PaymentSerializer(
                    change_payment(request, appointment_id, target_state=serializer.validated_data.pop("state"), **serializer.validated_data)
                ).data,
                200,
            ),
        )


def queue_summary(session):
    return {
        "queue_id": str(session.pk),
        "doctor": {"id": str(session.doctor_id), "display_name": session.doctor.display_name},
        "location": {"id": str(session.location_id), "name": session.location.name},
        "chamber": {"id": str(session.chamber_id), "name": session.chamber.name},
        "waiting_count": session.tickets.filter(state=QueueTicket.State.WAITING).count(),
        "state": session.state,
    }


class DashboardView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def get(self, request, role):
        if role not in active_roles(request.user):
            return Response({"detail": "The requested dashboard role is not active.", "code": "role_not_active"}, status=403)
        hospital = Hospital.objects.filter(is_active=True).first()
        if hospital:
            today = timezone.now().astimezone(hospital_zone(hospital)).date()
            day_start, day_end = local_day_bounds(hospital, today)
            appointments_today = Appointment.objects.filter(
                hospital=hospital,
                start_at__gte=day_start,
                start_at__lt=day_end,
            )
        else:
            today = timezone.localdate()
            appointments_today = Appointment.objects.none()
        if role == "patient":
            queryset = appointment_queryset(request)
            summary = {
                "upcoming_appointments": queryset.filter(
                    status=Appointment.Status.CONFIRMED,
                    start_at__gte=timezone.now(),
                ).count(),
                "completed": queryset.filter(status=Appointment.Status.COMPLETED).count(),
                "unread_notifications": request.user.notifications.filter(read_at__isnull=True).count(),
            }
            recent = AppointmentSerializer(queryset[:5], many=True).data
        elif role == "doctor":
            sessions = QueueSession.objects.filter(doctor__user=request.user, service_date=today).select_related("doctor", "location", "chamber")
            doctor_today = appointments_today.filter(doctor__user=request.user)
            recent_estimate = (
                QueueEstimateRecord.objects.filter(session__doctor__user=request.user)
                .order_by("-created_at")
                .values_list("service_estimate", flat=True)
                .first()
            )
            if recent_estimate is not None:
                estimated_minutes = int(round(float(recent_estimate)))
            else:
                configured = list(Schedule.objects.filter(doctor__user=request.user, is_active=True).values_list("slot_duration_minutes", flat=True))
                estimated_minutes = int(round(sum(configured) / len(configured))) if configured else None
            summary = {
                "today_appointments": doctor_today.count(),
                "completed": doctor_today.filter(status=Appointment.Status.COMPLETED).count(),
                "waiting": QueueTicket.objects.filter(
                    session__in=sessions,
                    state=QueueTicket.State.WAITING,
                ).count(),
                "active_queues": sessions.filter(state=QueueSession.State.OPEN).count(),
                "estimated_minutes": estimated_minutes,
            }
            recent = [queue_summary(item) for item in sessions[:25]]
        elif role == "receptionist":
            sessions = QueueSession.objects.filter(service_date=today).select_related("doctor", "location", "chamber")
            waiting = QueueTicket.objects.filter(session__in=sessions, state=QueueTicket.State.WAITING).count()
            summary = {
                "today_appointments": appointments_today.count(),
                "checked_in": QueueTicket.objects.filter(session__in=sessions).count(),
                "waiting": waiting,
                "unpaid": PaymentRecord.objects.filter(appointment__in=appointments_today, state=PaymentRecord.State.UNPAID).count(),
            }
            recent = [queue_summary(item) for item in sessions[:100]]
        else:
            from communications.models import NotificationOutbox

            waiting_now = QueueTicket.objects.filter(
                session__service_date=today,
                state=QueueTicket.State.WAITING,
            ).count()
            notification_failures = NotificationOutbox.objects.filter(state__in=[NotificationOutbox.State.FAILED, NotificationOutbox.State.DEAD]).count()
            summary = {
                "active_doctors": DoctorProfile.objects.filter(is_active=True).count(),
                "active_schedules": Schedule.objects.filter(is_active=True).count(),
                "today_appointments": appointments_today.count(),
                "waiting_now": waiting_now,
                "notification_failures": notification_failures,
            }
            recent = []
        return Response({"role": role, "summary": summary, "recent": recent})


class DoctorScheduleView(APIView):
    permission_classes = [IsOperationalStaff]

    def get(self, request):
        if "doctor" not in active_roles(request.user):
            return Response({"detail": "Doctor role is not active.", "code": "role_not_active"}, status=403)
        schedules = (
            Schedule.objects.filter(doctor__user=request.user, is_active=True)
            .select_related("hospital", "doctor", "location", "chamber")
            .prefetch_related("doctor__departments")
        )
        return Response(ScheduleSerializer(schedules, many=True).data)


class AuditListView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        from core.models import AuditEvent

        queryset = AuditEvent.objects.select_related("actor")
        event_type = request.query_params.get("event_type", "").strip()
        if event_type:
            if len(event_type) > 100:
                return Response({"detail": "event_type is too long.", "code": "invalid_filter"}, status=400)
            queryset = queryset.filter(event_type=event_type)
        for field in ("request_id", "subject_id"):
            value = request.query_params.get(field, "").strip()
            if value:
                try:
                    value = uuid.UUID(value)
                except ValueError:
                    return Response({"detail": f"{field} must be a UUID.", "code": "invalid_filter"}, status=400)
                queryset = queryset.filter(**{field: value})
        actor = request.query_params.get("actor", "").strip()
        if actor:
            if len(actor) > 254:
                return Response({"detail": "actor is too long.", "code": "invalid_filter"}, status=400)
            try:
                queryset = queryset.filter(actor_id=uuid.UUID(actor))
            except ValueError:
                if "@" not in actor:
                    return Response({"detail": "actor must be a staff UUID or exact email address.", "code": "invalid_filter"}, status=400)
                queryset = queryset.filter(actor__email__iexact=actor)
        bounds = {}
        for key in ("from", "to"):
            raw = request.query_params.get(key, "").strip()
            if not raw:
                continue
            value = parse_datetime(raw)
            if not value:
                day = parse_date(raw)
                if day:
                    value = datetime.combine(day, time.min if key == "from" else time.max)
            if not value:
                return Response({"detail": f"{key} must be an ISO date or datetime.", "code": "invalid_filter"}, status=400)
            if timezone.is_naive(value):
                value = timezone.make_aware(value, timezone.get_current_timezone())
            bounds[key] = value
        if bounds.get("from") and bounds.get("to") and bounds["to"] < bounds["from"]:
            return Response({"detail": "to cannot be earlier than from.", "code": "invalid_filter"}, status=400)
        if bounds.get("from") and bounds.get("to") and bounds["to"] - bounds["from"] > timedelta(days=366):
            return Response({"detail": "Audit date ranges are limited to 366 days.", "code": "invalid_filter"}, status=400)
        if bounds.get("from"):
            queryset = queryset.filter(created_at__gte=bounds["from"])
        if bounds.get("to"):
            queryset = queryset.filter(created_at__lte=bounds["to"])
        queryset = queryset.order_by("-created_at", "-id")
        paginator = BoundedPagination()
        events = paginator.paginate_queryset(queryset, request, view=self)
        audit(request, "audit.search", None, "search", {"result_count": len(events)})
        return paginator.get_paginated_response(
            [
                {
                    "id": str(item.pk),
                    "event_type": item.event_type,
                    "actor_id": str(item.actor_id) if item.actor_id else None,
                    "actor_role": item.actor_role,
                    "subject_type": item.subject_type,
                    "subject_id": str(item.subject_id) if item.subject_id else None,
                    "action": item.action,
                    "changes": item.changes,
                    "reason": item.reason,
                    "request_id": str(item.request_id),
                    "created_at": item.created_at,
                }
                for item in events
            ]
        )
