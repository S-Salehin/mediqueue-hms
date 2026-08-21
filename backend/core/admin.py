from django.contrib import admin

from .models import AuditEvent, IdempotencyRecord


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "action", "actor", "subject_type", "created_at", "request_id")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]
    search_fields = ("event_type", "action", "request_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ("scope", "actor", "state", "created_at", "expires_at")
    readonly_fields = [field.name for field in IdempotencyRecord._meta.fields]
