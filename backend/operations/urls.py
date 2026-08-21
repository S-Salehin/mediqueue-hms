from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AppointmentDetailView,
    AppointmentListCreateView,
    AuditListView,
    AvailabilityView,
    CallNextView,
    CancelView,
    CheckInView,
    DashboardView,
    DoctorScheduleView,
    PatientLeaveQueueView,
    PaymentActionView,
    PaymentView,
    QueueSnapshotView,
    RescheduleView,
    ScheduleAdminViewSet,
    ScheduleExceptionAdminViewSet,
    WalkInView,
    action_view,
)

router = SimpleRouter()
router.register("admin/schedules", ScheduleAdminViewSet)
router.register("admin/schedule-exceptions", ScheduleExceptionAdminViewSet)

urlpatterns = [
    path("public/doctors/<uuid:doctor_id>/availability/", AvailabilityView.as_view()),
    path("appointments/", AppointmentListCreateView.as_view()),
    path("appointments/<uuid:appointment_id>/", AppointmentDetailView.as_view()),
    path("appointments/<uuid:appointment_id>/reschedule/", RescheduleView.as_view()),
    path("appointments/<uuid:appointment_id>/cancel/", CancelView.as_view()),
    path("reception/appointments/<uuid:appointment_id>/check-in/", CheckInView.as_view()),
    path("reception/walk-ins/", WalkInView.as_view()),
    path("queues/<uuid:queue_id>/snapshot/", QueueSnapshotView.as_view()),
    path("queues/<uuid:queue_id>/call-next/", CallNextView.as_view()),
    path("queue-tickets/<uuid:ticket_id>/start/", action_view("start").as_view()),
    path("queue-tickets/<uuid:ticket_id>/defer/", action_view("defer").as_view()),
    path("queue-tickets/<uuid:ticket_id>/restore/", action_view("restore").as_view()),
    path("queue-tickets/<uuid:ticket_id>/complete/", action_view("complete").as_view()),
    path("queue-tickets/<uuid:ticket_id>/no-show/", action_view("no_show").as_view()),
    path("queue-tickets/<uuid:ticket_id>/cancel/", action_view("cancel").as_view()),
    path("queue-tickets/<uuid:ticket_id>/leave/", PatientLeaveQueueView.as_view()),
    path("appointments/<uuid:appointment_id>/payment/", PaymentView.as_view()),
    path("appointments/<uuid:appointment_id>/payment/actions/", PaymentActionView.as_view()),
    path("dashboards/<str:role>/", DashboardView.as_view()),
    path("doctor/schedules/", DoctorScheduleView.as_view()),
    path("admin/schedules/<uuid:pk>/deactivate/", ScheduleAdminViewSet.as_view({"post": "deactivate"})),
    path("admin/audit-events/", AuditListView.as_view()),
    path("", include(router.urls)),
]
