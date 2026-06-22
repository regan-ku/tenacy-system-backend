from django.core.exceptions import ValidationError
from ..models import Agency, AgencyDirector, AgencyVerification, DelegatedProperty

def validate_agency_activation(agency: Agency):
    """
    Validates if an agency meets all requirements to be marked as ACTIVE.
    Rule: Must have a verified business record AND at least one verified director.
    """
    verification = getattr(agency, 'verification_record', None)
    if not verification or verification.status != AgencyVerification.Status.VERIFIED:
        raise ValidationError("Agency business verification must be approved before activation.")
        
    has_verified_director = agency.directors.filter(
        verification_status=AgencyDirector.VerificationStatus.VERIFIED
    ).exists()
    
    if not has_verified_director:
        raise ValidationError("At least one agency director must be verified before activation.")

def validate_delegation_request(landlord_user, agency: Agency, property_ref):
    """
    Validates the preconditions for a landlord delegating a property to an agency.
    """
    if property_ref.created_by != landlord_user and property_ref.owner != landlord_user:
        raise ValidationError("You do not have ownership rights to delegate this property.")
        
    if agency.status not in [Agency.Status.VERIFIED, Agency.Status.ACTIVE]:
        raise ValidationError("Cannot delegate to an unverified or suspended agency.")
        
    # Check if already actively delegated to this agency
    if DelegatedProperty.objects.filter(
        property_ref=property_ref,
        agency=agency,
        status=DelegatedProperty.Status.ACTIVE
    ).exists():
        raise ValidationError("This property is already actively delegated to this agency.")

def validate_staff_assignment(agency: Agency, user, role: str):
    """
    Validates preconditions for assigning a user as agency staff.
    """
    from ..models import AgencyStaff
    
    if AgencyStaff.objects.filter(agency=agency, user=user, status='active').exists():
        raise ValidationError("This user is already an active staff member of this agency.")
        
    valid_roles = [choice[0] for choice in AgencyStaff.StaffRole.choices]
    if role not in valid_roles:
        raise ValidationError(f"Invalid staff role. Must be one of: {', '.join(valid_roles)}")