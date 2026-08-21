from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AccountToken, LoginAudit, RoleAssignment, StaffInvitation, StaffMFADevice, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "display_name", "is_active", "is_staff", "email_verified_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identity", {"fields": ("display_name", "email_verified_at")}),
        ("Access", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2", "is_staff", "is_active")}),)
    search_fields = ("email", "display_name")


admin.site.register(RoleAssignment)
admin.site.register(StaffInvitation)
admin.site.register(StaffMFADevice)
admin.site.register(AccountToken)


@admin.register(LoginAudit)
class LoginAuditAdmin(admin.ModelAdmin):
    readonly_fields = [field.name for field in LoginAudit._meta.fields]
    list_display = ("result", "user", "created_at", "request_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
