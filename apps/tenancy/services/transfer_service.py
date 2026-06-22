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
    def execute_transfer(transfer_request: TenancyTransfer, approved_by) -> Tenancy:
        """
        Executes an approved transfer request.
        1. Terminates old tenancy.
        2. Releases old unit to marketplace.
        3. Creates new tenancy for destination unit.
        4. Occupies new unit (removes from marketplace).
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
        ).first()

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
        OccupancyService.mark_unit_vacant(transfer_request.from_unit, old_tenancy)

        # 6. Create new tenancy for destination unit
        new_tenancy = TenancyService.create_tenancy(
            tenant=transfer_request.tenant,
            unit=transfer_request.to_unit,
            property_obj=transfer_request.to_property,
            created_by=approved_by,
            rent_amount=transfer_request.to_unit.rent_amount, # Use new unit's pricing
            deposit_amount=transfer_request.to_unit.deposit_amount,
            service_charge_amount=transfer_request.to_unit.service_charge,
            tenancy_type=old_tenancy.tenancy_type,
            start_date=timezone.now().date(),
            end_date=old_tenancy.end_date # Carry over original end date, or adjust as needed
        )

        # 7. If the old tenancy was fully paid/waived, we can auto-activate the new one 
        # (assuming deposit/service charge logic carries over, otherwise it stays pending_payment)
        if old_tenancy.is_ready_for_activation():
            # For simplicity in transfer, we assume financial obligations are settled or carried over
            new_tenancy.deposit_paid = old_tenancy.deposit_paid or old_tenancy.deposit_waived
            new_tenancy.service_charge_paid = old_tenancy.service_charge_paid or old_tenancy.service_charge_waived
            new_tenancy.save(update_fields=['deposit_paid', 'service_charge_paid'])
            
            TenancyService.activate_tenancy(new_tenancy, activated_by=approved_by)

        # 8. Update transfer request status
        transfer_request.transfer_status = 'completed'
        transfer_request.approved_by = approved_by
        transfer_request.processed_at = timezone.now()
        transfer_request.save(update_fields=['transfer_status', 'approved_by', 'processed_at'])

        return new_tenancy