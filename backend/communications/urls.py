from django.urls import path

from .views import FailedOutboxRetryView, FailedOutboxView, NotificationListView, NotificationReadView, PreferenceView

urlpatterns = [
    path("notifications/", NotificationListView.as_view()),
    path("notifications/<uuid:notification_id>/read/", NotificationReadView.as_view()),
    path("notification-preferences/", PreferenceView.as_view()),
    path("admin/notification-outbox/", FailedOutboxView.as_view()),
    path("admin/notification-outbox/<uuid:outbox_id>/retry/", FailedOutboxRetryView.as_view()),
    path("admin/notifications/", FailedOutboxView.as_view()),
]
