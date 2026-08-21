import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AppendOnlyModel(TimeStampedUUIDModel):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and self.__class__.objects.filter(pk=self.pk).exists():
            raise ValidationError("Append only records cannot be changed.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Append only records cannot be deleted.")


class AuditEvent(AppendOnlyModel):
    event_type = models.CharField(max_length=80, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    actor_role = models.CharField(max_length=20, blank=True)
    subject_type = models.CharField(max_length=80)
    subject_id = models.UUIDField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=80)
    changes = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    request_id = models.UUIDField(db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event_type", "created_at"])]


class IdempotencyRecord(TimeStampedUUIDModel):
    class State(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scope = models.CharField(max_length=160)
    key_digest = models.CharField(max_length=64)
    request_digest = models.CharField(max_length=64)
    state = models.CharField(max_length=20, choices=State.choices, default=State.PROCESSING)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor", "scope", "key_digest"], name="unique_idempotency_scope_key")]
        indexes = [models.Index(fields=["expires_at"])]


class RateLimitBucket(models.Model):
    key_digest = models.CharField(max_length=64, primary_key=True)
    scope = models.CharField(max_length=40)
    request_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["scope", "expires_at"])]
