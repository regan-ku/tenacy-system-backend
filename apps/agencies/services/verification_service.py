from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import Agency, AgencyVerification, AgencyActivityLog
from ..utils.validation_utils import validate_agency_activation
from .agency_service import AgencyService
from .director_service import DirectorService

class AgencyVerificationService:
    """
    Handles the business verification workflow for agencies.
    Ensures all compliance documents are submitted and approved before activation.
    """

    @staticmethod
    @transaction.atomic
    def submit_business_verification(agency: Agency, submitted_by_user, data: dict, files: dict) -> AgencyVerification:
        """
        Submits or updates business verification documents for an agency.
        """
        if agency.status == Agency.Status.ACTIVE:
            raise ValidationError("This agency is already verified and active.")

        verification, created = AgencyVerification.objects.get_or_create(agency=agency)
        
        # Update text fields
        if 'kra_pin' in data:
            verification.kra_pin = data['kra_pin']
            
        # Note: File fields (business_registration_cert, kra_tax_compliance_cert, agency_license) 
        # are typically handled by the DRF serializer, but we reset status here.
        verification.status = AgencyVerification.Status.PENDING
        verification.submitted_at = timezone.now()
        verification.save()
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.VERIFICATION_SUBMITTED,
            performed_by=submitted_by_user,
            details={"step": "business_documents_submitted"}
        )
        return verification

    @staticmethod
    @transaction.atomic
    def review_business_verification(verification: AgencyVerification, admin_reviewer, status: str, reason: str = "") -> AgencyVerification:
        """
        Admin action to approve or reject the agency's business verification.
        If approved, it attempts to activate the agency (which also checks director verification).
        """
        agency = verification.agency
        
        if status == 'verified':
            # Before approving business verification, ensure at least one director is verified
            if not DirectorService.check_agency_director_requirements(agency):
                raise ValidationError("Cannot approve agency verification: At least one agency director must be verified first.")
                
            verification.mark_verified(admin_reviewer)
            
            # Attempt full agency activation
            try:
                AgencyService.activate_agency(agency, admin_reviewer)
            except ValidationError as e:
                # Fallback if activation fails for any other reason
                raise ValidationError(f"Verification approved, but activation failed: {str(e)}")
                
            action_type = AgencyActivityLog.ActionType.VERIFICATION_APPROVED
            
        elif status in ['rejected', 'resubmit']:
            if not reason:
                raise ValidationError("A reason is required for rejection or resubmission.")
            verification.mark_rejected(admin_reviewer, reason)
            action_type = AgencyActivityLog.ActionType.VERIFICATION_REJECTED
        else:
            raise ValidationError("Invalid status provided.")
            
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=action_type,
            performed_by=admin_reviewer,
            details={
                "verification_id": verification.id,
                "status": status,
                "reason": reason
            }
        )
        return verification