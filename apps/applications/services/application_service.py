from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import Application
from apps.properties.models import Unit

# Safely import sub-models if they exist
try:
    from ..models import RentalApplication
except ImportError:
    RentalApplication = None

User = get_user_model()

class ApplicationService:
    """
    Handles the creation and lifecycle management of applications.
    """
    MAX_APPLICATIONS_PER_UNIT = 30

    @staticmethod
    @transaction.atomic
    def create_rental_application(
        applicant,
        unit: Unit, 
        employment_status: str, 
        desired_move_in_date
    ) -> Application:
        """
        Creates a new rental application.
        """
        # ✅ 1. ENFORCE NO DUPLICATE APPLICATIONS RULE
        # Checks if the applicant already has an active, pending, or approved application for THIS exact unit.
        existing_application = Application.objects.filter(
            applicant=applicant,
            unit=unit,
            status__in=['pending', 'under_review', 'approved', 'escalated']
        ).exists()

        if existing_application:
            raise ValidationError(
                "You have already applied for this unit. Please wait for a decision or withdraw your previous application."
            )

        # 2. ENFORCE MAX APPLICATIONS RULE
        current_app_count = Application.objects.filter(
            unit=unit, 
            status__in=['pending', 'under_review', 'escalated']
        ).count()

        if current_app_count >= ApplicationService.MAX_APPLICATIONS_PER_UNIT:
            raise ValidationError(
                f"This unit has reached the maximum limit of {ApplicationService.MAX_APPLICATIONS_PER_UNIT} active applications."
            )

        # 3. Validate unit is actually available for applications
        if unit.status != 'available':
            raise ValidationError("This unit is not currently available for applications.")

        # 4. Create base application
        create_kwargs = {
            'applicant': applicant,
            'property': unit.property_ref, 
            'unit': unit,
            'status': 'pending'
        }
        
        if hasattr(Application, 'ApplicationType'):
            create_kwargs['application_type'] = Application.ApplicationType.RENTAL
        else:
            create_kwargs['application_type'] = 'rental'
            
        application = Application.objects.create(**create_kwargs)

        # 5. Create specific rental details
        if RentalApplication is not None:
            try:
                RentalApplication.objects.create(
                    application=application,
                    employment_status=employment_status,
                    desired_move_in_date=desired_move_in_date
                )
            except Exception:
                application.message = f"Employment: {employment_status}, Move-in: {desired_move_in_date}"
                application.save(update_fields=['message'])
        else:
            application.message = f"Employment: {employment_status}, Move-in: {desired_move_in_date}"
            application.save(update_fields=['message'])

        return application