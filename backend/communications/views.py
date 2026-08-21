import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import BoundedPagination
from core.permissions import IsAdministrator, IsAuthenticatedWithStaffMFA
from core.services import audit, idempotent
from core.throttling import DatabaseScopedRateThrottle

from .models import Notification, NotificationOutbox, NotificationPreference
from .serializers import NotificationPreferenceSerializer, NotificationSerializer, OutboxRetrySerializer
from .services import secure_link_is_active


class NotificationListView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def get(self, request):
        queryset = request.user.notifications.order_by("-created_at", "-id")
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(NotificationSerializer(page, many=True).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def post(self, request, notification_id):
        notification = Notification.objects.filter(pk=notification_id, user=request.user).first()
        if not notification:
            return Response({"detail": "Notification not found.", "code": "not_found"}, status=404)
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(notification).data)


class PreferenceView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def _get(self, request):
        preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return preference

    def get(self, request):
        return Response(NotificationPreferenceSerializer(self._get(request)).data)

    def patch(self, request):
        protected = {"appointment_email", "queue_email"} & set(request.data)
        if protected:
            return Response(
                {
                    "detail": "Use the consent workflow to change email delivery consent.",
                    "code": "consent_required",
                },
                status=409,
            )
        preference = self._get(request)
        serializer = NotificationPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        def operation():
            locked = NotificationPreference.objects.select_for_update().get(pk=preference.pk)
            before = {"in_app": locked.in_app}
            saved = NotificationPreferenceSerializer(locked, data=request.data, partial=True)
            saved.is_valid(raise_exception=True)
            saved.save()
            audit(
                request,
                "notification.preferences_updated",
                saved.instance,
                "update",
                {"before": before, "after": {"in_app": saved.instance.in_app}},
            )
            return saved.data, 200

        return idempotent(request, f"notification.preferences.{request.user.pk}", operation)


class FailedOutboxView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        queryset = NotificationOutbox.objects.all()
        state = request.query_params.get("status", "").strip()
        if state:
            if state not in NotificationOutbox.State.values:
                return Response({"detail": "Unknown notification status.", "code": "invalid_status"}, status=400)
            queryset = queryset.filter(state=state)
        queryset = queryset.order_by("-created_at", "-id")
        paginator = BoundedPagination()
        jobs = paginator.paginate_queryset(queryset, request, view=self)
        audit(request, "notification.outbox_reviewed", None, "search", {"result_count": len(jobs)})
        return paginator.get_paginated_response(
            [
                {
                    "id": str(job.pk),
                    "channel": "email",
                    "event_type": job.template_key,
                    "template_key": job.template_key,
                    "status": job.state,
                    "state": job.state,
                    "attempt_count": job.attempt_count,
                    "next_attempt_at": job.next_attempt_at,
                    "last_error_category": job.last_error_category,
                    "created_at": job.created_at,
                }
                for job in jobs
            ]
        )


class FailedOutboxRetryView(APIView):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, outbox_id):
        serializer = OutboxRetrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            job = NotificationOutbox.objects.select_for_update().filter(pk=outbox_id).first()
            if not job:
                return {"detail": "Notification job not found.", "code": "not_found"}, 404
            if job.state != NotificationOutbox.State.FAILED:
                return {
                    "detail": "Only a failed notification can be retried. Start a new secure workflow for dead token emails.",
                    "code": "notification_not_retryable",
                }, 409
            if job.template_key in {"verify_email", "reset_password", "claim_patient", "staff_invitation"} and not secure_link_is_active(job):
                job.state = NotificationOutbox.State.DEAD
                job.template_data = {}
                job.last_error_category = "expired_or_superseded"
                job.save(update_fields=["state", "template_data", "last_error_category", "updated_at"])
                return {
                    "detail": "The secure link expired or was superseded. Start the account workflow again.",
                    "code": "secure_link_inactive",
                }, 409
            job.state = NotificationOutbox.State.PENDING
            job.next_attempt_at = timezone.now() + timedelta(seconds=secrets.randbelow(16))
            job.leased_at = None
            job.last_error_category = ""
            job.save(
                update_fields=[
                    "state",
                    "next_attempt_at",
                    "leased_at",
                    "last_error_category",
                    "updated_at",
                ]
            )
            audit(
                request,
                "notification.retry_requested",
                job,
                "retry",
                {"attempt_count": job.attempt_count, "state": job.state},
                serializer.validated_data["reason"],
            )
            return {
                "id": str(job.pk),
                "status": job.state,
                "state": job.state,
                "attempt_count": job.attempt_count,
                "next_attempt_at": job.next_attempt_at,
            }, 200

        return idempotent(request, f"notification.outbox.{outbox_id}.retry", operation)
