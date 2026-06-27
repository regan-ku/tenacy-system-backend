from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Tenancy, Occupancy
from ..services.validation_service import TenancyValidationService
from ..services.occupancy_service import OccupancyService

class TenancyService:
    """
    Core business logic for tenancy lifecycle management.
    """

    @staticmethod
    @transaction.atomic
    def create_tenancy(
        tenant, unit, property_obj, created_by, 
        rent_amount, deposit_amount, service_charge_amount, 
        tenancy_type='rental', start_date=None, end_date=None
    ) -> Tenancy:
        """
        Creates a new tenancy record in 'pending_payment' status.
        Does NOT activate it until financial conditions are met.
        """
        # 1. Validate unit is actually available
        TenancyValidationService.validate_unit_availability(unit)
        
        # 2. Validate tenant eligibility
        TenancyValidationService.validate_tenant_eligibility(tenant, property_obj)

        # 3. Create tenancy record
        tenancy = Tenancy.objects.create(
            tenant=tenant,
            unit=unit,
            property=property_obj,
            created_by=created_by,
            tenancy_type=tenancy_type,
            rent_amount=rent_amount,
            deposit_amount=deposit_amount,
            service_charge_amount=service_charge_amount,
            status=Tenancy.Status.PENDING_PAYMENT,
            start_date=start_date or timezone.now().date(),
            end_date=end_date
        )
        return tenancy

    @staticmethod
    @transaction.atomic
    def activate_tenancy(tenancy: Tenancy, activated_by) -> Tenancy:
        """
        Transitions a tenancy from PENDING_PAYMENT to ACTIVE.
        Strictly enforces that deposit and service charge are paid or waived.
        """
        # 1. Validate financial readiness
        TenancyValidationService.validate_activation_readiness(tenancy)

        # 2. Update status
        tenancy.status = Tenancy.Status.ACTIVE
        tenancy.save(update_fields=['status'])

        # 3. Trigger occupancy update (which syncs with marketplace)
        OccupancyService.mark_unit_occupied(tenancy.unit, tenancy.tenant, tenancy)

        # ✅ 4. CRITICAL: Mark the linked application as 'completed'
        # This removes it from the Agency Operations grid and registers it under tenancy.
        from apps.applications.models import Application
        linked_application = Application.objects.filter(
            applicant=tenancy.tenant,
            unit=tenancy.unit,
            status='approved'  # Only mark approved applications as completed
        ).first()

        if linked_application:
            linked_application.status = Application.Status.COMPLETED
            linked_application.save(update_fields=['status'])

        return tenancy

    @staticmethod
    @transaction.atomic
    def suspend_tenancy(tenancy: Tenancy, reason: str) -> Tenancy:
        """
        Temporarily suspends a tenancy (e.g., due to severe arrears or breach).
        Does NOT release the unit occupancy.
        """
        if tenancy.status not in [Tenancy.Status.ACTIVE, Tenancy.Status.EXTENDED]:
            raise ValidationError("Only active or extended tenancies can be suspended.")
            
        tenancy.status = Tenancy.Status.SUSPENDED
        tenancy.save(update_fields=['status'])
        return tenancy