from rest_framework import permissions
from typing import Optional

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
        prop = getattr(tenancy, "target_property", None)
        if prop:
            if prop.created_by == request.user:
                return True
            if getattr(prop, "current_manager", None) == request.user:
                return True
        return False

class CanTriggerPaymentRequest(permissions.BasePermission):
    """
    Restricts STK push / payment initiation to verified staff, finance officers, or system services.
    Prevents tenants or unauthorized agents from initiating outbound payment requests.
    Matches §3.1, §7.1 (Secure payment initiation & direct collection)
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            request.user.is_staff or 
            getattr(request.user, "role", None) in ["finance", "manager", "admin"]
        )

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
            
        prop = getattr(tenancy, "target_property", None)
        if prop and (prop.created_by == request.user or getattr(prop, "current_manager", None) == request.user):
            return True
        return False

class CanManagePaymentAccounts(permissions.BasePermission):
    """
    Controls setup, verification, and modification of routing accounts (Paybill/Till/Phone).
    Only landlords, verified agencies, and admins can configure collection endpoints.
    Matches §2.1-2.3, §2.27-2.29 (Payment account verification & direct routing)
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
            getattr(request.user, "role", None) == "finance"
        )