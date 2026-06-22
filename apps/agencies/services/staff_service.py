from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from ..models import Agency, AgencyStaff, AgencyRole, AgencyPermission, AgencyActivityLog
from ..utils.validation_utils import validate_staff_assignment
from ..utils.role_helpers import get_effective_permissions

class StaffService:
    """
    Manages internal staff hierarchy, role assignment, and permission delegation.
    """

    @staticmethod
    @transaction.atomic
    def create_staff_member(agency: Agency, created_by_user, user, role: str, contact_phone=None, contact_email=None) -> AgencyStaff:
        """Adds a user as agency staff. Validates role and agency status."""
        if agency.status != Agency.Status.ACTIVE:
            raise ValidationError("Cannot add staff to an inactive or unverified agency.")
            
        validate_staff_assignment(agency, user, role)
        
        staff = AgencyStaff.objects.create(
            agency=agency,
            user=user,
            role=role,
            contact_phone=contact_phone,
            contact_email=contact_email
        )
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.STAFF_CREATED,
            performed_by=created_by_user,
            target_user=user,
            details={"staff_id": staff.id, "assigned_role": role}
        )
        return staff

    @staticmethod
    @transaction.atomic
    def assign_property_permissions(staff_member: AgencyStaff, property_ref, permission_overrides: dict) -> AgencyPermission:
        """Grants or overrides permissions for a specific delegated property."""
        DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
        delegation = DelegatedProperty.objects.filter(
            agency=staff_member.agency, property_ref=property_ref, status='active'
        ).first()
        
        if not delegation:
            raise ValidationError("This property is not actively delegated to your agency.")
            
        permission, _ = AgencyPermission.objects.update_or_create(
            staff_member=staff_member,
            scope='property_specific',
            delegated_property=delegation,
            defaults={'permissions': permission_overrides}
        )
        
        AgencyActivityLog.objects.create(
            agency=staff_member.agency,
            action_type='staff_permissions_assigned',
            performed_by=permission.granted_by or staff_member.user,
            target_user=staff_member.user,
            details={"property_id": property_ref.id, "permissions": permission_overrides}
        )
        return permission

    @staticmethod
    @transaction.atomic
    def deactivate_staff(staff_member: AgencyStaff, terminated_by_user, reason: str = "") -> AgencyStaff:
        """Safely deactivates staff access while preserving audit history."""
        staff_member.status = AgencyStaff.Status.TERMINATED
        staff_member.terminated_at = timezone.now()
        staff_member.notes = reason
        staff_member.save(update_fields=['status', 'terminated_at', 'notes'])
        
        AgencyPermission.objects.filter(staff_member=staff_member).update(
            granted_by=terminated_by_user, updated_at=timezone.now()
        )
        
        AgencyActivityLog.objects.create(
            agency=staff_member.agency,
            action_type='staff_terminated',
            performed_by=terminated_by_user,
            target_user=staff_member.user,
            details={"staff_id": staff_member.id, "reason": reason}
        )
        return staff_member

    @staticmethod
    def resolve_staff_dashboard_state(staff_member: AgencyStaff) -> dict:
        """Routes staff to their operational dashboard based on effective permissions and workload."""
        effective_perms = get_effective_permissions(staff_member)
        
        Application = apps.get_model('applications', 'Application')
        MaintenanceRequest = apps.get_model('maintenance', 'MaintenanceRequest')
        
        delegated_ids = staff_member.agency.delegated_properties.filter(status='active').values_list('property_ref_id', flat=True)
        
        pending_apps = Application.objects.filter(property_id__in=delegated_ids, status='pending_review').count()
        open_maintenance = MaintenanceRequest.objects.filter(property_id__in=delegated_ids, status__in=['open', 'in_progress']).count()
        
        return {
            "staff_id": staff_member.id,
            "role": staff_member.role,
            "effective_permissions": effective_perms,
            "workload": {
                "pending_applications": pending_apps,
                "open_maintenance_tickets": open_maintenance
            },
            "next_route": "/dashboard/agency/operational" if effective_perms.get('can_manage_tenants') else "/dashboard/agency/view"
        }