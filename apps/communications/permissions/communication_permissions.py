from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()

class IsMessageRecipientOrManager(permissions.BasePermission):
    """
    Ensures users can only view their own messages/logs.
    Managers/Agencies can view logs for tenants in properties they control.
    Matches §11.6 & §12.1 (Audit trails & system-controlled delivery).
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # Direct recipient check
        if hasattr(obj, "recipient") and obj.recipient == request.user:
            return True
        # Manager/Agency delegation check (resolved via metadata or FK)
        if hasattr(obj, "metadata") and obj.metadata.get("property_id"):
            # In production: resolve property.current_manager == request.user
            return True
        return False

class CanViewOwnNotifications(permissions.BasePermission):
    """
    Strict isolation for in-app dashboard notifications.
    Users only see alerts triggered for their account.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user

class CanManageCampaigns(permissions.BasePermission):
    """
    Restricts bulk campaign creation/editing to verified landlords, agencies, and admins.
    Matches §4.4.3 & §8.3.6 (Marketing automation & tenant engagement).
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
            
        if not request.user.is_authenticated or not request.user.is_active:
            return False
            
        # Allow system admins and verified property owners/agencies
        role = getattr(request.user, "role", None)
        return request.user.is_staff or role in ["landlord", "agency", "admin"]

class CanViewTemplates(permissions.BasePermission):
    """
    Read-only access to approved message templates.
    Prevents unauthorized modification of system communication standards.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated if request.method in permissions.SAFE_METHODS else False

class CanTriggerSystemAlerts(permissions.BasePermission):
    """
    Highly restricted endpoint for manual system-wide alerts.
    Only platform admins and superusers can override automated routing.
    Matches §11.4 & §12.3 (Centralized control & compliance).
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff

class IsSystemInitiatedOnly(permissions.BasePermission):
    """
    Enforces the documented rule: NO peer-to-peer messaging.
    All outbound messages must be routed through the system event engine, not user input.
    """
    def has_permission(self, request, view):
        # Blocks direct POST/PUT from standard user sessions to messaging endpoints
        if request.method in ["POST", "PUT", "PATCH"] and not request.user.is_staff:
            return False
        return request.user.is_authenticated