from django.contrib import admin

from .models import Notification, NotificationAttempt, NotificationOutbox, NotificationPreference

admin.site.register(Notification)
admin.site.register(NotificationPreference)
admin.site.register(NotificationOutbox)


@admin.register(NotificationAttempt)
class NotificationAttemptAdmin(admin.ModelAdmin):
    readonly_fields = [field.name for field in NotificationAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
