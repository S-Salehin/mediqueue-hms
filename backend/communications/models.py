from django.conf import settings
from django.db import models

from core.models import AppendOnlyModel, TimeStampedUUIDModel


class Notification(TimeStampedUUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE)
    category = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=500)
    related_id = models.UUIDField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"])]


class NotificationPreference(TimeStampedUUIDModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="notification_preference", on_delete=models.CASCADE)
    appointment_email = models.BooleanField(default=False)
    queue_email = models.BooleanField(default=False)
    in_app = models.BooleanField(default=True)


class NotificationOutbox(TimeStampedUUIDModel):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        FAILED = "failed", "Failed"
        SENT = "sent", "Sent"
        DEAD = "dead", "Dead"

    recipient = models.EmailField()
    template_key = models.CharField(max_length=60)
    template_version = models.CharField(max_length=20, default="v1")
    template_data = models.JSONField(default=dict)
    related_id = models.UUIDField(null=True, blank=True, db_index=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    leased_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_category = models.CharField(max_length=60, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["state", "next_attempt_at"])]


class NotificationAttempt(AppendOnlyModel):
    outbox = models.ForeignKey(NotificationOutbox, related_name="attempts", on_delete=models.PROTECT)
    attempt_number = models.PositiveSmallIntegerField()
    result = models.CharField(max_length=20)
    safe_error_category = models.CharField(max_length=60, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["outbox", "attempt_number"], name="unique_outbox_attempt")]
