from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from ..models import AgencyStaff, AgencyPermission, AgencyActivityLog
from ..utils.role_helpers import get_effective_permissions, has_permission

class PermissionService:
    """
    Manages granular, property-specific permission overrides for agency staff.
    Ensures that staff access is strictly controlled and audited.
 """

    @staticmethod
    @transaction.atomic
    def grant_property_permission(staff_member: AgencyStaff, property_ref, granted_by_user, permissions_dict: dict) -> AgencyPermission:
        """
        Grants or updates specific permissions for a staff member on a specific delegated property.
        """
        DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
        
        # Ensure the property is actively delegated to this staff member's agency
        delegation = DelegatedProperty.objects.filter(
            agency=staff_member.agency,
            property_ref=property_ref,
            status='active'
        ).first()
        
        if not delegation:
            raise ValidationError("Cannot grant permissions: This property is not actively delegated to your agency.")

        # Validate that permissions_dict only contains allowed keys (optional but recommended for security)
        allowed_keys = [
            'can_manage_tenants', 'can_generate_invoices', 'can_reconcile_payments',
            'can_view_financials', 'can_manage_maintenance', 'can_edit_listings'
        ]
        for key in permissions_dict.keys():
            if key not in allowed_keys:
                raise ValidationError(f"Invalid permission key: {key}")

        permission, created = AgencyPermission.objects.update_or_create(
            staff_member=staff_member,
            scope='property_specific',
            delegated_property=delegation,
            defaults={
                'permissions': permissions_dict,
                'granted_by': granted_by_user
            }
        )
        
        AgencyActivityLog.objects.create(
            agency=staff_member.agency,
            action_type='staff_permissions_assigned',
            performed_by=granted_by_user,
            target_user=staff_member.user,
            details={
                "property_id": property_ref.id,
                "permissions_granted": permissions_dict,
                "created": created
            }
        )
        return permission

    @staticmethod
    @transaction.atomic
    def revoke_property_permission(staff_member: AgencyStaff, property_ref, revoked_by_user) -> bool:
        """
        Removes property-specific permission overrides, reverting the staff member to their base role permissions.
        """
        DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
        delegation = DelegatedProperty.objects.filter(
            agency=staff_member.agency,
            property_ref=property_ref,
            status='active'
        ).first()
        
        if not delegation:
            return False

        deleted_count, _ = AgencyPermission.objects.filter(
            staff_member=staff_member,
            scope='property_specific',
            delegated_property=delegation
        ).delete()
        
        if deleted_count > 0:
            AgencyActivityLog.objects.create(
                agency=staff_member.agency,
                action_type='staff_permissions_revoked',
                performed_by=revoked_by_user,
                target_user=staff_member.user,
                details={"property_id": property_ref.id}
            )
            return True
        return False

    @staticmethod
    def evaluate_staff_access(staff_member: AgencyStaff, permission_key: str, property_ref=None) -> bool:
        """
        Quick evaluation method to check if a staff member has a specific permission.
        Used by DRF Permission classes and internal service checks.
        """
        return has_permission(staff_member, permission_key, property_ref)