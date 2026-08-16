from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Tenancy, Occupancy
from ..services.validation_service import TenancyValidationService
from ..services.occupancy_service import OccupancyService
from apps.payments.services.billing_cycle_service import BillingCycleService
from apps.payments.services.invoice_service import InvoiceService
from apps.payments.models import TenantBalance

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
        
        # 4. ✅ Initialize TenantBalance record
        TenantBalance.objects.get_or_create(
            tenancy=tenancy,
            defaults={'total_paid': 0, 'total_invoiced': 0, 'current_balance': 0}
        )
        
        return tenancy

    @staticmethod
    @transaction.atomic
    def activate_tenancy(tenancy: Tenancy, activated_by) -> Tenancy:
        """
        Transitions a tenancy from PENDING_PAYMENT to ACTIVE.
        Generates the Move-In Invoice and sets the initial billing cursor.
        """
        # 1. Validate financial readiness (Deposit + Service Charge paid/waived)
        TenancyValidationService.validate_activation_readiness(tenancy)

        # 2. ✅ Generate the unified Move-In Invoice (Rent + Deposit + Service Charge)
        # This ensures the tenant has a paper trail for their initial payments
        InvoiceService.generate_move_in_invoice(tenancy)

        # 3. ✅ Set initial next_billing_date based on unit's billing cycle
        cycle = getattr(tenancy.unit.unit_group, 'billing_cycle', None) or getattr(tenancy.unit, 'billing_cycle', None)
        if cycle:
            cycle_type = cycle if isinstance(cycle, str) else getattr(cycle, 'cycle_type', 'monthly')
            config = BillingCycleService.get_cycle_config(cycle_type)
            billing_day = getattr(tenancy.unit, 'billing_day', config['billing_day'])
            
            tenancy.next_billing_date = BillingCycleService.calculate_next_billing_date(
                tenancy.start_date, 
                cycle_type, 
                billing_day
            )
        
        # 4. Update status
        tenancy.status = Tenancy.Status.ACTIVE
        tenancy.save(update_fields=['status', 'next_billing_date'])

        # 5. Trigger occupancy update (which syncs with marketplace)
        OccupancyService.mark_unit_occupied(tenancy.unit, tenancy.tenant, tenancy)

        # 6. Mark the linked application as 'completed'
        from apps.applications.models import Application
        linked_application = Application.objects.filter(
            applicant=tenancy.tenant,
            unit=tenancy.unit,
            status='approved'
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