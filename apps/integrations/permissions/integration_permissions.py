from rest_framework import permissions

class IsAdminOrSystemIntegrator(permissions.BasePermission):
    """
    Restricted to Superusers, System Admins, or designated Integration Managers.
    Grants access to logs, webhook events, payment transaction history, and configs.
    """
    def has_permission(self, request, view):
        # Check for specific roles if defined, else fallback to staff
        return request.user.is_authenticated and (
            request.user.is_staff or 
            getattr(request.user, 'role', None) in ['admin', 'integrator']
        )

class IsCampaignManager(permissions.BasePermission):
    """
    Allows creation/editing of marketing campaigns.
    Open to Marketing, Managers, and Admins.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = getattr(request.user, 'role', '')
        return role in ['marketing', 'manager', 'admin', 'staff']

class CanTriggerPayment(permissions.BasePermission):
    """
    Highly restricted. Only specific service accounts or authorized staff can initiate STK pushes.
    """
    def has_permission(self, request, view):
        # In production, this often checks for a specific API Token or 'finance' role
        return request.user.is_authenticated and request.user.is_staff

class IsWebhookService(permissions.BasePermission):
    """
    Used for inbound webhook endpoints (M-Pesa, WhatsApp).
    These endpoints shouldn't require standard user auth, but should verify the source IP/Signature.
    """
    def has_permission(self, request, view):
        # Bypass standard DRF auth; security handled by signature validation in views/services
        return True

class ReadOnlyAudience(permissions.BasePermission):
    """
    Allows viewing campaign audiences without modifying settings.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return IsCampaignManager().has_permission(request, view)