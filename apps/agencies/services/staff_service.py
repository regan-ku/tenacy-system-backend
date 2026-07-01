from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.apps import apps
from ..models import Agency, AgencyStaff, AgencyActivityLog

class StaffService:
    """
    Manages internal agency staff hierarchy, property assignments, and deactivation.
    Fully aligned with the new PropertyStaffAssignment architecture.
    """

    @staticmethod
    @transaction.atomic
    def create_staff_member(agency: Agency, created_by_user, user, role: str, contact_phone=None, contact_email=None) -> AgencyStaff:
        """
        Links an existing user to an agency as staff. 
        (Note: For creating brand new staff accounts with Ghost Profiles, 
        use UserService.create_staff_for_manager instead).
        """
        if agency.status != Agency.Status.ACTIVE:
            raise ValidationError("Cannot add staff to an inactive or unverified agency.")
            
        if AgencyStaff.objects.filter(agency=agency, user=user, status=AgencyStaff.Status.ACTIVE).exists():
            raise ValidationError("This user is already an active staff member of this agency.")

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
    def assign_staff_to_property(staff_member: AgencyStaff, property_ref, assigning_user, operational_role: str, notes: str = None):
        """
        Assigns an agency staff member to a specific property with an operational role.
        Delegates to the PropertyService to ensure strict ownership and delegation rules are enforced.
        """
        PropertyService = apps.get_model('properties', 'PropertyService')
        
        # Ensure the property is actively delegated to this staff member's agency
        DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
        delegation = DelegatedProperty.objects.filter(
            agency=staff_member.agency, 
            property_ref=property_ref, 
            status='active'
        ).first()
        
        if not delegation:
            raise ValidationError("Cannot assign staff: This property is not actively delegated to your agency.")

        # Use the unified PropertyService to handle the assignment and business rules
        return PropertyService.assign_staff_to_property(
            property_obj=property_ref,
            user_to_assign=staff_member.user,
            assigning_user=assigning_user,
            operational_role=operational_role,
            notes=notes
        )

    @staticmethod
    @transaction.atomic
    def remove_staff_from_property(staff_member: AgencyStaff, property_ref, removing_user):
        """
        Removes a staff member's operational assignment from a specific property.
        """
        PropertyService = apps.get_model('properties', 'PropertyService')
        
        return PropertyService.terminate_staff_assignment(
            property_obj=property_ref,
            user_to_remove=staff_member.user,
            assigning_user=removing_user
        )

    @staticmethod
    @transaction.atomic
    def deactivate_staff(staff_member: AgencyStaff, terminated_by_user, reason: str = "") -> AgencyStaff:
        """
        Safely deactivates staff access.
        1. Terminates the AgencyStaff record.
        2. Auto-terminates all PropertyStaffAssignment records.
        3. Deactivates the underlying User account.
        """
        # 1. Terminate Agency Staff record
        staff_member.status = AgencyStaff.Status.TERMINATED
        staff_member.terminated_at = timezone.now()
        staff_member.notes = reason
        staff_member.save(update_fields=['status', 'terminated_at', 'notes'])
        
        # 2. Auto-terminate all active property assignments
        PropertyStaffAssignment = apps.get_model('properties', 'PropertyStaffAssignment')
        terminated_assignments = PropertyStaffAssignment.objects.filter(
            user=staff_member.user,
            is_active=True
        ).update(
            is_active=False, 
            terminated_at=timezone.now(),
            notes=f"Auto-terminated due to agency staff revocation: {reason}"
        )
        
        # 3. Deactivate the underlying User account
        user = staff_member.user
        if user.is_active:
            user.is_active = False
            user.save(update_fields=['is_active'])
        
        # 4. Audit Log
        AgencyActivityLog.objects.create(
            agency=staff_member.agency,
            action_type='staff_terminated',
            performed_by=terminated_by_user,
            target_user=user,
            details={
                "staff_id": staff_member.id, 
                "reason": reason,
                "property_assignments_terminated": terminated_assignments
            }
        )
        return staff_member

    @staticmethod
    def get_staff_dashboard_state(staff_member: AgencyStaff) -> dict:
        """
        Routes staff to their operational dashboard based on their PropertyStaffAssignments.
        Replaces the old AgencyPermission-based dashboard routing.
        """
        PropertyStaffAssignment = apps.get_model('properties', 'PropertyStaffAssignment')
        Application = apps.get_model('applications', 'Application')
        MaintenanceRequest = apps.get_model('maintenance', 'MaintenanceRequest')
        
        # Get IDs of properties this staff member is actively assigned to
        assigned_property_ids = PropertyStaffAssignment.objects.filter(
            user=staff_member.user,
            is_active=True
        ).values_list('property_id', flat=True)
        
        # Calculate workload based on assigned properties
        pending_apps = Application.objects.filter(
            property_id__in=assigned_property_ids, 
            status__in=['pending', 'under_review']
        ).count()
        
        open_maintenance = MaintenanceRequest.objects.filter(
            property_id__in=assigned_property_ids, 
            status__in=['open', 'in_progress', 'assigned']
        ).count()
        
        # Determine primary operational role from assignments
        primary_role = PropertyStaffAssignment.objects.filter(
            user=staff_member.user,
            is_active=True
        ).values_list('operational_role', flat=True).first() or staff_member.role
        
        return {
            "staff_id": staff_member.id,
            "agency_role": staff_member.role,
            "primary_operational_role": primary_role,
            "assigned_properties_count": len(assigned_property_ids),
            "workload": {
                "pending_applications": pending_apps,
                "open_maintenance_tickets": open_maintenance
            },
            "next_route": f"/dashboard/{staff_member.role}"
        }