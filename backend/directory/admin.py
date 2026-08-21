from django.contrib import admin

from .models import Chamber, ConsentRecord, Department, DoctorProfile, Hospital, Location, MRNSequence, PatientProfile, PrivacyNoticeVersion

admin.site.register(Hospital)
admin.site.register(Department)
admin.site.register(Location)
admin.site.register(Chamber)
admin.site.register(DoctorProfile)
admin.site.register(PatientProfile)
admin.site.register(MRNSequence)


class AppendOnlyAdmin(admin.ModelAdmin):
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(PrivacyNoticeVersion, AppendOnlyAdmin)
admin.site.register(ConsentRecord, AppendOnlyAdmin)
