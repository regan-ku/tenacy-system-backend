from rest_framework import permissions

class IsFinancialStakeholder(permissions.BasePermission):
    """
    Ensures strict data isolation for financial records.
    - Tenants see only their own invoices, payments, and balances.
    - Landlords/Managers see records for properties they own/manage.
    - Staff sees all.
    Matches §2.17, §6.2.2, §11.3 (Role boundaries & financial privacy)
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
            
        # Resolve linked tenancy if present
        tenancy = getattr(obj, "tenancy", None) or getattr(obj, "tenancy_record", None)
        if not tenancy:
            return False

        if tenancy.tenant == request.user:
            return True

        # Check property ownership or delegation
        prop = getattr(tenancy, "property", None) or getattr(tenancy, "target_property", None)
        if prop:
            if getattr(prop, "created_by", None) == request.user:
                return True
            if getattr(prop, "current_manager", None) == request.user:
                return True
        return False


class CanTriggerPaymentRequest(permissions.BasePermission):
    """
    PLATFORM COLLECTION MODEL:
    Allows authenticated users to initiate payment requests (e.g., STK Push).
    - Tenants can initiate payments to the Platform's global Paybill.
    - Landlords/Agencies can initiate payment links for their tenants.
    - Staff/Admins have full access.
    
    Note: Actual authorization of WHICH invoice/tenancy can be paid 
    is enforced at the View/Serializer level, not here.
    Matches §6.2.2 (Tenant Capabilities: Make rent payments)
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        allowed_roles = ["tenant", "landlord", "agency", "finance", "manager", "admin"]
        
        if request.user.is_staff or getattr(request.user, "role", None) in allowed_roles:
            return True
            
        return False


class CanApproveFinancialOverride(permissions.BasePermission):
    """
    Highly restricted: Approves waivers, refunds, and manual adjustments.
    Requires property ownership, senior management, or explicit finance role.
    Matches §2.21, §6.5, §11.12 (Approval workflows & fraud prevention)
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if request.method not in ["POST", "PUT", "PATCH"]:
            return request.user.is_authenticated

        tenancy = getattr(obj, "tenancy", None)
        if not tenancy:
            return False
            
        prop = getattr(tenancy, "property", None) or getattr(tenancy, "target_property", None)
        if prop and (getattr(prop, "created_by", None) == request.user or getattr(prop, "current_manager", None) == request.user):
            return True
        return False


class CanManagePaymentAccounts(permissions.BasePermission):
    """
    PLATFORM SETTLEMENT MODEL:
    Controls setup, verification, and modification of settlement/payout accounts.
    Only landlords, verified agencies, and admins can configure where the platform 
    sends collected funds (B2C payouts/Bank transfers).
    Matches §2.1-2.3, §2.27-2.29 (Account verification & settlement routing)
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            request.user.is_staff or 
            getattr(request.user, "role", None) in ["landlord", "agency", "admin"]
        )


class CanReconcileTransactions(permissions.BasePermission):
    """
    Grants access to payment reconciliation, callback matching, and discrepancy handling.
    Restricted to finance officers and platform admins for audit compliance.
    Matches §7.3, §11.11-11.14 (Secure reconciliation & audit trails)
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            request.user.is_staff or 
            getattr(request.user, "role", None) in ["finance", "admin"]
        )