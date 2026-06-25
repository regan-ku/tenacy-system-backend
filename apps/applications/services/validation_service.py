from django.core.exceptions import ValidationError
from ..models import Application
from apps.properties.models import Unit

# ✅ CRITICAL FIX: Use the full app path for cross-app imports. 
# 'from tenancy.models' causes a fatal ModuleNotFoundError.
from apps.tenancy.models import Tenancy

class ApplicationValidationService:
    """
    Handles pre-submission validation for all application types.
    Prevents duplicate submissions, spam, and invalid state transitions.
    """

    @staticmethod
    def validate_rental_application_submission(applicant, unit: Unit) -> None:
        """
        Validates that a user can submit a rental application for a specific unit.
        """
        if unit.status != 'available':
            raise ValidationError("This unit is no longer available for applications.")

        # Check for duplicate active applications
        duplicate = Application.objects.filter(
            applicant=applicant,
            unit=unit,
            application_type=Application.ApplicationType.RENTAL,
            status__in=['pending', 'under_review', 'escalated']
        ).exists()

        if duplicate:
            raise ValidationError("You already have a pending application for this unit.")

        # ✅ FIX: Safe property access (handles property_ref or property)
        property_obj = getattr(unit, 'property_ref', None) or getattr(unit, 'property', None)
        
        # Check if the user is already an active tenant in this specific unit
        active_tenancy = Tenancy.objects.filter(
            tenant=applicant,
            unit=unit,
            status__in=['active', 'extended', 'pending_payment']
        ).exists()

        if active_tenancy:
            raise ValidationError("You already have an active tenancy in this unit.")

    @staticmethod
    def validate_transfer_application_submission(applicant, from_unit: Unit, to_unit: Unit) -> None:
        """
        Validates that a transfer request is logically sound before creation.
        """
        if from_unit.id == to_unit.id:
            raise ValidationError("Source and destination units cannot be the same.")

        # Check if user actually occupies the source unit
        active_tenancy = Tenancy.objects.filter(
            tenant=applicant,
            unit=from_unit,
            status__in=['active', 'extended']
        ).exists()

        if not active_tenancy:
            raise ValidationError("You do not have an active tenancy in the source unit.")

        if to_unit.status != 'available':
            raise ValidationError("The requested destination unit is not available.")