from rest_framework.permissions import BasePermission, IsAuthenticated


def active_roles(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(user.role_assignments.filter(is_active=True).values_list("role", flat=True))


class HasAnyRole(BasePermission):
    allowed_roles = set()

    def has_permission(self, request, view):
        matched = active_roles(request.user) & set(getattr(view, "allowed_roles", self.allowed_roles))
        if not matched:
            return False
        staff_roles = {"doctor", "receptionist", "administrator"}
        if matched & staff_roles and not request.session.get("mfa_verified", False):
            return False
        return True


class IsAuthenticatedWithStaffMFA(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if active_roles(request.user) & {"doctor", "receptionist", "administrator"}:
            return bool(request.session.get("mfa_verified", False))
        return True


class IsAdministrator(HasAnyRole):
    allowed_roles = {"administrator"}


class IsOperationalStaff(HasAnyRole):
    allowed_roles = {"doctor", "receptionist", "administrator"}


class IsReceptionOrAdmin(HasAnyRole):
    allowed_roles = {"receptionist", "administrator"}
