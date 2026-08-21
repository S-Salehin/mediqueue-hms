from django.contrib import admin

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

admin.site.register(Schedule)
admin.site.register(ScheduleException)
admin.site.register(Appointment)
admin.site.register(QueueSession)
admin.site.register(QueueTicket)
admin.site.register(PaymentRecord)


class AppendOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(AppointmentHistory, AppendOnlyAdmin)
admin.site.register(QueueEvent, AppendOnlyAdmin)
admin.site.register(QueueEstimateRecord, AppendOnlyAdmin)
admin.site.register(PaymentHistory, AppendOnlyAdmin)
