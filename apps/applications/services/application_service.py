from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser  # ✅ Added for proper type hinting

from ..models import Application, RentalApplication, TransferApplication, EvictionApplication
from apps.properties.models import Unit

# Used for runtime logic (e.g., querying)
User = get_user_model()

class ApplicationService:
    """
    Handles the creation and lifecycle management of applications.
    Enforces strict limits (e.g., max 30 applications per unit) to prevent spam and manage workload.
    """

    MAX_APPLICATIONS_PER_UNIT = 30

    @staticmethod
    @transaction.atomic
    def create_rental_application(
        applicant: AbstractUser,  # ✅ Fixed type hint
        unit: Unit, 
        employment_status: str, 
        desired_move_in_date
    ) -> Application:
        """
        Creates a new rental application.
        Auto-populates applicant details via FK and enforces the 30-application limit per unit.
        """
        # 1. ENFORCE MAX APPLICATIONS RULE
        current_app_count = Application.objects.filter(
            unit=unit, 
            application_type=Application.ApplicationType.RENTAL,
            status__in=['pending', 'under_review', 'escalated']
        ).count()

        if current_app_count >= ApplicationService.MAX_APPLICATIONS_PER_UNIT:
            raise ValidationError(
                f"This unit has reached the maximum limit of {ApplicationService.MAX_APPLICATIONS_PER_UNIT} active applications. "
                "Please check back later or view other available units."
            )

        # 2. Validate unit is actually available for applications
        if unit.status != 'available':
            raise ValidationError("This unit is not currently available for applications.")

        # 3. Create base application
        application = Application.objects.create(
            applicant=applicant,
            property=unit.property,
            unit=unit,
            application_type=Application.ApplicationType.RENTAL,
            status=Application.Status.PENDING
        )

        # 4. Create specific rental details (applicant details are linked via FK, no redundant data entry)
        RentalApplication.objects.create(
            application=application,
            employment_status=employment_status,
            desired_move_in_date=desired_move_in_date
        )

        return application

    @staticmethod
    @transaction.atomic
    def create_transfer_application(
        applicant: AbstractUser,  # ✅ Fixed type hint
        current_tenancy, 
        to_unit: Unit, 
        reason: str
    ) -> Application:
        """
        Creates a transfer application for an existing tenant.
        """
        # 1. Validate tenant actually occupies the source unit
        if current_tenancy.tenant != applicant or current_tenancy.status not in ['active', 'extended']:
            raise ValidationError("You do not have an active tenancy in the specified source unit.")

        # 2. Validate target unit is available
        if to_unit.status != 'available':
            raise ValidationError("The requested destination unit is not available.")

        # 3. Create base application
        application = Application.objects.create(
            applicant=applicant,
            property=to_unit.property,
            unit=to_unit,
            application_type=Application.ApplicationType.TRANSFER,
            status=Application.Status.PENDING
        )

        # 4. Create specific transfer details
        TransferApplication.objects.create(
            application=application,
            current_tenancy=current_tenancy,
            from_property=current_tenancy.property,
            from_unit=current_tenancy.unit,
            to_property=to_unit.property,
            to_unit=to_unit,
            reason=reason
        )

        return application

    @staticmethod
    @transaction.atomic
    def create_eviction_application(
        applicant: AbstractUser,  # ✅ Fixed type hint
        unit: Unit, 
        notice_period_days: int, 
        intended_vacate_date, 
        reason_for_leaving: str = "", 
        forwarding_address: str = ""
    ) -> Application:
        """
        Creates a tenant-initiated eviction/termination notice.
        """
        # Validate tenant has an active tenancy in this unit
        from apps.tenancy.models import Tenancy  # ✅ Fixed import path
        
        active_tenancy = Tenancy.objects.filter(
            tenant=applicant, 
            unit=unit, 
            status__in=['active', 'extended']
        ).first()
        
        if not active_tenancy:
            raise ValidationError("You do not have an active tenancy in this unit to terminate.")

        application = Application.objects.create(
            applicant=applicant,
            property=unit.property,
            unit=unit,
            application_type=Application.ApplicationType.EVICTION_NOTICE,
            status=Application.Status.PENDING
        )

        EvictionApplication.objects.create(
            application=application,
            notice_period_days=notice_period_days,
            intended_vacate_date=intended_vacate_date,
            reason_for_leaving=reason_for_leaving,
            forwarding_address=forwarding_address
        )

        return application