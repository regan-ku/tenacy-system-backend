from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Tenancy, TenancyTransfer, TenancyHistory
from ..services.tenancy_service import TenancyService
from ..services.occupancy_service import OccupancyService

class TransferService:
    """
    Handles tenant movement between units/properties.
    STRICT RULE: Transfers are ONLY allowed between properties under the EXACT SAME management.
    """

    @staticmethod
    def validate_same_management(from_property, to_property) -> None:
        """
        CRITICAL RULE: Ensures both properties share the same owner (created_by) 
        AND the same current manager. Prevents cross-agency/cross-landlord transfers.
        """
        if from_property.created_by_id != to_property.created_by_id:
            raise ValidationError("Transfers are only allowed between properties owned by the same landlord.")
            
        if from_property.current_manager_id != to_property.current_manager_id:
            raise ValidationError("Transfers are only allowed between properties managed by the same entity (landlord or agency).")

    @staticmethod
    @transaction.atomic
    def execute_transfer(transfer_request: TenancyTransfer, approved_by, auto_activate: bool = False) -> Tenancy:
        """
        Executes an approved transfer request.
        ✅ UPDATED: auto_activate defaults to False to enforce the "wait for payment/waiver" rule.
        """
        # 1. Validate same management rule
        TransferService.validate_same_management(transfer_request.from_property, transfer_request.to_property)

        # 2. Validate destination unit is available
        from ..services.validation_service import TenancyValidationService
        TenancyValidationService.validate_unit_availability(transfer_request.to_unit)

        # 3. Find the active tenancy to transfer
        old_tenancy = Tenancy.objects.filter(
            tenant=transfer_request.tenant,
            unit=transfer_request.from_unit,
            status__in=['active', 'extended', 'pending_payment']
        ).select_related('unit', 'property').first()

        if not old_tenancy:
            raise ValidationError("No active tenancy found for the source unit.")

        # 4. Archive old tenancy to history
        TenancyHistory.objects.create(
            tenant=old_tenancy.tenant,
            unit=old_tenancy.unit,
            property=old_tenancy.property,
            tenancy_type=old_tenancy.tenancy_type,
            start_date=old_tenancy.start_date,
            end_date=timezone.now().date(),
            final_status='transferred',
            termination_reason=f"Transferred to {transfer_request.to_unit.unit_code}",
            manager_notes=transfer_request.reason
        )

        # 5. Mark old tenancy as transferred and release old unit
        old_tenancy.status = Tenancy.Status.TRANSFERRED
        old_tenancy.save(update_fields=['status'])
        
        # ✅ Explicitly release occupancy
        OccupancyService.mark_unit_vacant(transfer_request.from_unit, old_tenancy)

        # 6. Create new tenancy for destination unit
        new_tenancy = TenancyService.create_tenancy(
            tenant=transfer_request.tenant,
            unit=transfer_request.to_unit,
            property_obj=transfer_request.to_property,
            created_by=approved_by,
            rent_amount=transfer_request.to_unit.rent_amount,
            deposit_amount=transfer_request.to_unit.deposit_amount,
            service_charge_amount=transfer_request.to_unit.service_charge,
            tenancy_type=old_tenancy.tenancy_type,
            start_date=timezone.now().date(),
            end_date=old_tenancy.end_date
        )

        # ✅ CRITICAL: DO NOT carry over payment status automatically.
        # The new tenancy must remain 'pending_payment' until the manager applies waivers 
        # or the tenant pays for the new unit, enforcing the unified business rule.
        if auto_activate and new_tenancy.is_ready_for_activation():
            TenancyService.activate_tenancy(new_tenancy, activated_by=approved_by)

        # 8. Update transfer request status
        transfer_request.transfer_status = 'completed'
        transfer_request.approved_by = approved_by
        transfer_request.processed_at = timezone.now()
        transfer_request.save(update_fields=['transfer_status', 'approved_by', 'processed_at'])

        return new_tenancy

    @staticmethod
    @transaction.atomic
    def execute_direct_manager_transfer(
        tenant, from_unit, to_unit, reason, approved_by, auto_activate: bool = False
    ) -> tuple[Tenancy, TenancyTransfer]:
        """
        For paper-based or manager-initiated transfers that bypass the application system.
        ✅ UPDATED: auto_activate defaults to False
        """
        from apps.properties.models import Unit
        from ..models import TenancyTransfer
        
        from_unit_obj = Unit.objects.select_related('property').get(id=from_unit.id if hasattr(from_unit, 'id') else from_unit)
        to_unit_obj = Unit.objects.select_related('property').get(id=to_unit.id if hasattr(to_unit, 'id') else to_unit)
        
        transfer_record = TenancyTransfer.objects.create(
            tenant=tenant,
            from_property=from_unit_obj.property,
            from_unit=from_unit_obj,
            to_property=to_unit_obj.property,
            to_unit=to_unit_obj,
            reason=reason or "Manager-initiated transfer",
            requested_by=approved_by,
            transfer_status='approved',
            approved_by=approved_by,
            processed_at=timezone.now()
        )
        
        new_tenancy = TransferService.execute_transfer(
            transfer_request=transfer_record,
            approved_by=approved_by,
            auto_activate=auto_activate
        )
        
        return new_tenancy, transfer_record