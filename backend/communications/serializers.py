from rest_framework import serializers

from accounts.serializers import StrictSerializer

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "category", "title", "body", "related_id", "created_at", "read_at")


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ("appointment_email", "queue_email", "in_app", "updated_at")
        read_only_fields = ("appointment_email", "queue_email", "updated_at")


class OutboxRetrySerializer(StrictSerializer):
    reason = serializers.CharField(min_length=3, max_length=500)
