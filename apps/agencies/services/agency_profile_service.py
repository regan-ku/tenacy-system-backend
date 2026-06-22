from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import Agency, AgencyProfile

class AgencyProfileService:
    """
    Manages the business-level profile of an agency.
    Ensures corporate details are complete for tenancy applications or compliance.
    """

    @staticmethod
    @transaction.atomic
    def create_or_update_profile(agency: Agency, profile_data: dict) -> AgencyProfile:
        """
        Creates or updates the business profile for an agency.
        Auto-evaluates completeness based on mandatory corporate fields.
        """
        # Enforce that registration number matches the main agency record to prevent fraud
        if profile_data.get('registration_number') and profile_data['registration_number'] != agency.registration_number:
            raise ValidationError("Profile registration number must match the agency's official registration number.")

        profile, created = AgencyProfile.objects.update_or_create(
            agency=agency,
            defaults=profile_data
        )
        
        # The model's save() method auto-evaluates is_profile_complete
        # But we can explicitly call it or rely on the model's save() trigger
        profile.save() 
        
        return profile

    @staticmethod
    def get_profile(agency: Agency) -> AgencyProfile:
        """
        Retrieves the business profile, creating a blank one if it doesn't exist.
        """
        profile, created = AgencyProfile.objects.get_or_create(agency=agency)
        return profile

    @staticmethod
    def validate_profile_completeness(agency: Agency) -> bool:
        """
        Checks if the agency's business profile meets all requirements 
        (e.g., before allowing the agency to submit a rental application as a corporate tenant).
        """
        profile = getattr(agency, 'business_profile', None)
        if not profile:
            return False
            
        return profile.is_profile_complete