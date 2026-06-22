from rest_framework import permissions
from ..models import Dashboard, ReportSchedule

class CanViewDashboard(permissions.BasePermission):
    """
    Ensures a user can only view the dashboard configuration assigned to their specific role.
    Prevents lower-level roles (e.g., Caretakers, Agents) from accessing financial or admin dashboards.
    """
    def has_permission(self, request, view):
        # Admins can view any dashboard configuration for testing/setup
        if request.user.role == 'admin':
            return True
            
        # Users can only request the dashboard matching their current role
        requested_role = view.kwargs.get('role', request.user.role)
        return requested_role == request.user.role


class CanGenerateReport(permissions.BasePermission):
    """
    Restricts heavy report generation to authorized roles.
    Tenants and Caretakers cannot generate system-wide financial or occupancy reports.
    """
    def has_permission(self, request, view):
        allowed_roles = ['admin', 'landlord', 'agency', 'manager']
        return request.user.is_authenticated and request.user.role in allowed_roles


class CanManageReportSchedules(permissions.BasePermission):
    """
    Ensures users can only view, edit, or delete report schedules they personally created,
    unless they are an Admin.
    """
    def has_object_permission(self, request, view, obj):
        if not isinstance(obj, ReportSchedule):
            return True
            
        # Admins can manage all schedules
        if request.user.role == 'admin':
            return True
            
        # Users can only manage their own schedules
        return obj.created_by == request.user


class CanExportData(permissions.BasePermission):
    """
    Restricts CSV/Excel/PDF export endpoints to authorized roles.
    """
    def has_permission(self, request, view):
        # Tenants can only export their own payment receipts, handled at the view level.
        # For general report exports, restrict to management roles.
        allowed_roles = ['admin', 'landlord', 'agency', 'manager', 'agent']
        return request.user.is_authenticated and request.user.role in allowed_roles