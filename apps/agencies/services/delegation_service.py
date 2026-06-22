from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import Agency, DelegatedProperty, AgencyActivityLog
from ..utils.validation_utils import validate_delegation_request

class DelegationService:
    """
    Manages the delegation of property control. 
    Supports both Agency-initiated onboarding and Landlord-initiated delegation.
    """

    @staticmethod
    @transaction.atomic
    def agency_initiates_management(agency: Agency, landlord_user, property_ref, delegation_type: str = 'full', custom_permissions: dict = None) -> DelegatedProperty:
        """PATH 1: Agency creates or claims management of a property on behalf of a landlord."""
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
            delegation_type=delegation_type,
            custom_permissions=custom_permissions or {},
            status=DelegatedProperty.Status.ACTIVE,
            start_date=timezone.now().date()
        )
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_GRANTED,
            performed_by=landlord_user,
            details={"property_id": property_ref.id, "delegation_type": delegation_type, "initiated_by": "agency"}
        )
        return delegation

    @staticmethod
    @transaction.atomic
    def landlord_delegates_property(landlord_user, agency: Agency, property_ref, delegation_type: str, start_date, end_date=None, custom_permissions: dict = None) -> DelegatedProperty:
        """PATH 2: Landlord actively delegates an existing property to an agency."""
        validate_delegation_request(landlord_user, agency, property_ref)
        
        delegation = DelegatedProperty.objects.create(
            property_ref=property_ref,
            agency=agency,
            delegation_type=delegation_type,
            custom_permissions=custom_permissions or {},
            status=DelegatedProperty.Status.ACTIVE,
            start_date=start_date,
            end_date=end_date
        )
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_GRANTED,
            performed_by=landlord_user,
            details={"property_id": property_ref.id, "delegation_type": delegation_type, "initiated_by": "landlord"}
        )
        return delegation

    @staticmethod
    @transaction.atomic
    def revoke_delegation(delegation: DelegatedProperty, revoking_user, reason: str) -> DelegatedProperty:
        """Landlord or Admin revokes agency control. Fully reversible."""
        if delegation.status != DelegatedProperty.Status.ACTIVE:
            raise ValidationError("Cannot revoke an inactive or already revoked delegation.")
            
        delegation.revoke(revoking_user, reason)
        
        AgencyActivityLog.objects.create(
            agency=delegation.agency,
            action_type=AgencyActivityLog.ActionType.DELEGATION_REVOKED,
            performed_by=revoking_user,
            details={"property_id": delegation.property_ref.id, "reason": reason, "revoked_at": timezone.now().isoformat()}
        )
        return delegation

    @staticmethod
    def get_agency_delegated_portfolio(agency: Agency) -> list:
        """Returns all active delegations with formatted details and effective permissions."""
        from ..utils.role_helpers import get_delegation_details
        
        active_delegations = agency.delegated_properties.select_related('property_ref', 'agency').filter(status='active')
        return [get_delegation_details(delegation) for delegation in active_delegations]