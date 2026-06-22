from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Application
from apps.properties.models import Unit

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
        # 1. Check if unit is actually available
        if unit.status != 'available':
            raise ValidationError("This unit is no longer available for applications.")

        # 2. Check for duplicate active applications from the same user for the same unit
        duplicate = Application.objects.filter(
            applicant=applicant,
            unit=unit,
            application_type=Application.ApplicationType.RENTAL,
            status__in=['pending', 'under_review', 'escalated']
        ).exists()

        if duplicate:
            raise ValidationError("You already have a pending application for this unit.")

        # 3. Check if the user is already an active tenant in this specific unit
        from tenancy.models import Tenancy
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
        from tenancy.models import Tenancy
        active_tenancy = Tenancy.objects.filter(
            tenant=applicant,
            unit=from_unit,
            status__in=['active', 'extended']
        ).exists()

        if not active_tenancy:
            raise ValidationError("You do not have an active tenancy in the source unit.")

        if to_unit.status != 'available':
            raise ValidationError("The requested destination unit is not available.")