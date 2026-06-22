# backend/apps/accounts/services/verification_service.py
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Verification, User

class VerificationService:
    """
    Handles identity and business verification workflows.
    """

    @staticmethod
    def submit_verification(user: User, data: dict, files: dict) -> Verification:
        """
        Initiates or updates a verification request for Landlords/Agencies.
        """
        if user.role not in [User.Role.LANDLORD, User.Role.AGENCY]:
            raise ValidationError("Verification is only required for Landlords and Agencies.")

        verification, created = Verification.objects.get_or_create(user=user)
        
        if verification.status == 'verified':
            raise ValidationError("Account is already verified.")

        # Update text fields
        if 'kra_pin' in data:
            verification.kra_pin = data['kra_pin']
            
        # Files are typically handled by the serializer, but we update status here
        verification.status = 'pending'
        verification.submitted_at = timezone.now()
        verification.save()
        
        return verification

    @staticmethod
    def review_verification(verification_id: int, reviewer: User, status: str, reason: str = "") -> Verification:
        """
        Admin action to approve or reject a verification request.
        """
        if reviewer.role != User.Role.ADMIN:
            raise ValidationError("Only administrators can review verifications.")

        verification = Verification.objects.get(id=verification_id)
        
        if status == 'verified':
            verification.mark_verified(reviewer)
        elif status in ['rejected', 'resubmit']:
            if not reason:
                raise ValidationError("A reason is required for rejection or resubmission.")
            verification.mark_rejected(reviewer, reason)
        else:
            raise ValidationError("Invalid status provided.")
            
        return verification