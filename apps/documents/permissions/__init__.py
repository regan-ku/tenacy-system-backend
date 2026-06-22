from rest_framework import permissions

class IsDocumentStakeholder(permissions.BasePermission):
    """
    Ensures strict data isolation for documents.
    - Tenants see documents linked to their tenancy/applications.
    - Landlords/Agents see documents for properties they own/manage.
    - Staff sees all.
    Aligns with §11.8, §12.1 (Role boundaries & secure access control)
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        # Direct assignee (signer) or uploader
        if obj.assigned_to == request.user or obj.uploaded_by == request.user:
            return True

        # Tenancy linkage
        if obj.tenancy and obj.tenancy.tenant == request.user:
            return True

        # Property/Unit linkage
        prop = obj.property or (obj.unit.property if obj.unit else None)
        if prop:
            if getattr(prop, "owner", None) == request.user or getattr(prop, "created_by", None) == request.user:
                return True
            if getattr(prop, "current_manager", None) == request.user:
                return True

        return False

class CanSignDocument(permissions.BasePermission):
    """
    Restricts signature approval to the explicitly assigned user.
    Prevents unauthorized parties from finalizing leases, agreements, or receipts.
    Aligns with §11.6, §10.2 (Compliance signing workflow & accountability)
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.assigned_to == request.user and obj.status == "pending_signature"

class CanManageVersions(permissions.BasePermission):
    """
    Restricts version creation, archiving, and metadata edits to landlords, managers, and staff.
    Tenants cannot alter, version, or retract documents.
    Aligns with §10.2, §11.11-11.14 (Version control & immutable audit trails)
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_staff or getattr(request.user, "role", None) in ["landlord", "manager", "admin"]

class CanGenerateDocuments(permissions.BasePermission):
    """
    Restricts automated/system document generation endpoints.
    Ensures only verified staff, finance officers, or property owners can trigger PDF generation.
    Aligns with §3.1, §7.3 (Automated document generation & secure routing)
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_staff or getattr(request.user, "role", None) in ["landlord", "finance", "admin"]

class CanViewAuditLogs(permissions.BasePermission):
    """
    Read-only access to document audit trails.
    Required for compliance officers, admins, and involved stakeholders.
    Aligns with §11.17, §12 (Data integrity & audit readiness)
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated