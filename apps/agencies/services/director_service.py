from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import Agency, AgencyDirector, AgencyActivityLog

class DirectorService:
    """
    Manages the lifecycle of Agency Directors, ensuring legal accountability 
    and enforcing the rule that an agency must have ≥ 1 verified director to activate.
    """

    @staticmethod
    @transaction.atomic
    def add_director(agency: Agency, created_by_user, full_name: str, national_id: str = None, 
                     passport_number: str = None, email: str = None, phone_number: str = None,
                     nationality: str = None, address: str = None, ownership_percentage: float = 0.00,
                     is_primary: bool = False) -> AgencyDirector:
        """
        Adds a director to the agency. Validates that either National ID or Passport is provided.
        """
        if not national_id and not passport_number:
            raise ValidationError("A director must have either a National ID or a Passport Number.")
            
        # Check for duplicate directors by ID/Passport across the system (optional but recommended for fraud prevention)
        if national_id and AgencyDirector.objects.filter(national_id=national_id).exists():
            raise ValidationError("A director with this National ID already exists in the system.")
        if passport_number and AgencyDirector.objects.filter(passport_number=passport_number).exists():
            raise ValidationError("A director with this Passport Number already exists in the system.")

        director = AgencyDirector.objects.create(
            agency=agency,
            full_name=full_name,
            national_id=national_id,
            passport_number=passport_number,
            email=email,
            phone_number=phone_number,
            nationality=nationality,
            address=address,
            ownership_percentage=ownership_percentage,
            is_primary_director=is_primary,
            verification_status=AgencyDirector.VerificationStatus.PENDING
        )
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type='director_added',
            performed_by=created_by_user,
            details={
                "director_id": director.id,
                "full_name": full_name,
                "is_primary": is_primary
            }
        )
        return director

    @staticmethod
    @transaction.atomic
    def verify_director(director: AgencyDirector, admin_reviewer, status: str, reason: str = "") -> AgencyDirector:
        """
        Admin action to approve or reject a director's identity verification.
        """
        if status not in ['verified', 'rejected', 'suspended']:
            raise ValidationError("Invalid verification status.")
            
        if status == 'verified':
            director.verification_status = AgencyDirector.VerificationStatus.VERIFIED
            action_type = 'director_verified'
        else:
            director.verification_status = AgencyDirector.VerificationStatus.REJECTED
            action_type = 'director_rejected'
            
        director.save(update_fields=['verification_status'])
        
        AgencyActivityLog.objects.create(
            agency=director.agency,
            action_type=action_type,
            performed_by=admin_reviewer,
            target_user=director.user, # If linked to a system user
            details={
                "director_id": director.id,
                "status": status,
                "reason": reason
            }
        )
        return director

    @staticmethod
    def check_agency_director_requirements(agency: Agency) -> bool:
        """
        Helper to check if the agency meets the minimum director verification requirement.
        """
        return agency.directors.filter(verification_status=AgencyDirector.VerificationStatus.VERIFIED).exists()