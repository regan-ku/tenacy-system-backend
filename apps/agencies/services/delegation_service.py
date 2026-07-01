from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import Agency, DelegatedProperty, AgencyActivityLog, AgencyStaff
from ..utils.validation_utils import validate_delegation_request
from .activity_service import ActivityService

class DelegationService:
    """
    Manages the FULL delegation of property control to an Agency.
    Supports Agency-initiated onboarding, Landlord-initiated delegation, 
    and Agency-initiated relinquishment.
    """

    @staticmethod
    def _migrate_staff_to_agency(property_ref, agency):
        """Migrates Landlord-assigned staff to the Agency upon full delegation."""
        from apps.properties.models.staff_assignment import PropertyStaffAssignment
        
        landlord_assignments = PropertyStaffAssignment.objects.filter(
            property=property_ref,
            is_active=True,
            assigned_by_entity_type=PropertyStaffAssignment.AssignmentSource.LANDLORD
        )
        
        count = landlord_assignments.update(
            assigned_by_entity_type=PropertyStaffAssignment.AssignmentSource.AGENCY,
            assigned_by_agency=agency
        )
        return count

    @staticmethod
    @transaction.atomic
    def agency_initiates_management(agency: Agency, landlord_user, property_ref) -> DelegatedProperty:
        """PATH 1: Agency claims full management of a property."""
        if agency.status != Agency.Status.ACTIVE:
            raise ValidationError("Agency must be fully verified and active to manage properties.")
            
        if landlord_user.role != 'landlord':
            raise ValidationError("Property owner must be a verified landlord.")

        if DelegatedProperty.objects.filter(
            property_ref=property_ref, agency=agency, status=DelegatedProperty.Status.ACTIVE
        ).exists():
            raise ValidationError("This property is already actively managed by this agency.")

        delegation = DelegatedProperty.objects.create(
            property_ref=property_ref,
            agency=agency,
            status=DelegatedProperty.Status.ACTIVE,
            start_date=timezone.now().date()
        )
        
        migrated_count = DelegationService._migrate_staff_to_agency(property_ref, agency)
        
        ActivityService.log_action(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_GRANTED,
            performed_by=landlord_user,
            details={"property_id": property_ref.id, "initiated_by": "agency", "staff_migrated_count": migrated_count}
        )
        return delegation

    @staticmethod
    @transaction.atomic
    def landlord_delegates_property(landlord_user, agency: Agency, property_ref, start_date, end_date=None) -> DelegatedProperty:
        """PATH 2: Landlord delegates full control to an agency."""
        validate_delegation_request(landlord_user, agency, property_ref)
        
        delegation = DelegatedProperty.objects.create(
            property_ref=property_ref,
            agency=agency,
            status=DelegatedProperty.Status.ACTIVE,
            start_date=start_date,
            end_date=end_date
        )
        
        migrated_count = DelegationService._migrate_staff_to_agency(property_ref, agency)
        
        ActivityService.log_action(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_GRANTED,
            performed_by=landlord_user,
            details={"property_id": property_ref.id, "initiated_by": "landlord", "staff_migrated_count": migrated_count}
        )
        return delegation

    @staticmethod
    @transaction.atomic
    def revoke_delegation(delegation: DelegatedProperty, revoking_user, reason: str) -> DelegatedProperty:
        """PATH 3: Landlord revokes agency control."""
        if delegation.status != DelegatedProperty.Status.ACTIVE:
            raise ValidationError("Cannot revoke an inactive or already revoked delegation.")
            
        delegation.revoke(revoking_user, reason)
        
        # Revert all agency assignments back to landlord
        from apps.properties.models.staff_assignment import PropertyStaffAssignment
        reverted_count = PropertyStaffAssignment.objects.filter(
            property=delegation.property_ref,
            is_active=True,
            assigned_by_agency=delegation.agency
        ).update(
            assigned_by_entity_type=PropertyStaffAssignment.AssignmentSource.LANDLORD,
            assigned_by_agency=None
        )
        
        ActivityService.log_action(
            agency=delegation.agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_REVOKED,
            performed_by=revoking_user,
            details={"property_id": delegation.property_ref.id, "reason": reason, "action_context": "Landlord Revoked", "staff_reverted_count": reverted_count}
        )
        return delegation

    # ✅ NEW: AGENCY RELINQUISHMENT LOGIC
    @staticmethod
    @transaction.atomic
    def relinquish_delegation(delegation: DelegatedProperty, relinquishing_user, reason: str) -> DelegatedProperty:
        """
        PATH 4: Agency voluntarily gives up management of a property.
        - Terminates access for Agency employees.
        - Reverts access for Landlord's migrated staff (e.g., Caretakers).
        - Triggers tenant notifications.
        """
        if delegation.status != DelegatedProperty.Status.ACTIVE:
            raise ValidationError("Cannot relinquish an inactive or already revoked delegation.")
            
        # 1. Revoke the delegation record
        delegation.revoke(relinquishing_user, reason)
        
        # 2. SMART STAFF ACCESS CONTROL
        from apps.properties.models.staff_assignment import PropertyStaffAssignment
        
        # Get all active assignments made by this agency for this property
        agency_assignments = PropertyStaffAssignment.objects.filter(
            property=delegation.property_ref,
            is_active=True,
            assigned_by_agency=delegation.agency
        )
        
        # Get the IDs of users who are actual employees of this agency
        agency_employee_ids = set(AgencyStaff.objects.filter(
            agency=delegation.agency,
            status=AgencyStaff.Status.ACTIVE
        ).values_list('user_id', flat=True))
        
        for assignment in agency_assignments:
            if assignment.user_id in agency_employee_ids:
                # Agency employee loses access to the property
                assignment.terminate()
            else:
                # Landlord's staff (migrated caretaker) retains access, revert to landlord
                assignment.assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.LANDLORD
                assignment.assigned_by_agency = None
                assignment.save(update_fields=['assigned_by_entity_type', 'assigned_by_agency'])
                
        # 3. TENANT NOTIFICATION TRIGGER
        from apps.tenancy.models import Tenancy
        active_tenancies = Tenancy.objects.filter(
            property=delegation.property_ref,
            status='active'
        ).select_related('tenant')
        
        tenant_ids = [t.tenant_id for t in active_tenancies]
        
        # Log the notification event (Actual SMS/Email dispatch handled by Communications app)
        if tenant_ids:
            AgencyActivityLog.objects.create(
                agency=delegation.agency,
                action_type="TENANT_NOTIFICATION_TRIGGERED",
                performed_by=relinquishing_user,
                details={
                    "property_id": delegation.property_ref.id,
                    "event": "agency_relinquished",
                    "notified_tenant_count": len(tenant_ids)
                }
            )
            
        # 4. Audit Log
        ActivityService.log_action(
            agency=delegation.agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_REVOKED,
            performed_by=relinquishing_user,
            details={
                "property_id": delegation.property_ref.id, 
                "reason": reason, 
                "action_context": "Agency Relinquished Management",
                "relinquished_at": timezone.now().isoformat()
            }
        )
        return delegation

    @staticmethod
    def get_agency_delegated_portfolio(agency: Agency) -> list:
        """Returns all active delegations with formatted details."""
        from ..utils.role_helpers import get_delegation_details
        active_delegations = agency.delegated_properties.select_related('property_ref', 'agency').filter(status='active')
        return [get_delegation_details(delegation) for delegation in active_delegations]