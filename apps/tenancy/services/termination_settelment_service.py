from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Tenancy, TenancyTermination
from apps.payments.services.refund_service import RefundService
from .termination_service import TerminationService
import logging

logger = logging.getLogger(__name__)

class TerminationSettlementService:
    """
    Calculates the financial settlement for a terminating tenancy.
    Formula: (Deposit Held) - (Penalties Applied) - (Outstanding Arrears) = Net Refund / Amount Owed
    """

    @staticmethod
    def calculate_settlement(tenancy: Tenancy, total_penalties: Decimal = Decimal("0.00")):
        """
        Calculates the final settlement breakdown without executing anything.
        Used by the frontend to show the manager the math before finalizing.
        """
        # 1. Get Deposit Held
        deposit_held = Decimal(str(tenancy.deposit_amount))
        
        # 2. Get Penalties Applied
        penalties = Decimal(str(total_penalties))
        
        # 3. Get Outstanding Arrears (Correctly linked from the Payments app Arrears model)
        arrears = Decimal("0.00")
        if hasattr(tenancy, 'arrears_record') and tenancy.arrears_record:
            arrears = Decimal(str(tenancy.arrears_record.total_outstanding))

        # 4. Calculate Net
        net_refund = deposit_held - penalties - arrears
        
        return {
            "deposit_held": str(deposit_held),
            "penalties_applied": str(penalties),
            "outstanding_arrears": str(arrears),
            "net_refund": str(max(Decimal("0.00"), net_refund)),
            "amount_owed_by_tenant": str(abs(net_refund)) if net_refund < 0 else "0.00",
            "requires_tenant_payment": net_refund < 0
        }

    @staticmethod
    @transaction.atomic
    def finalize_settlement_and_vacate(
        tenancy: Tenancy, 
        termination_record: TenancyTermination, 
        approved_by_user,
        manager_deductions: Decimal = Decimal("0.00"),
        waive_arrears: bool = False
    ):
        """
        Executes the final settlement, triggers refund/invoice, and vacates the unit.
        """
        # 1. Recalculate with any manual manager deductions (e.g., physical damages)
        total_penalties = Decimal(str(termination_record.penalty_applied)) + manager_deductions
        settlement = TerminationSettlementService.calculate_settlement(tenancy, total_penalties)
        
        arrears = Decimal(settlement["outstanding_arrears"])
        if waive_arrears:
            arrears = Decimal("0.00") # Manager forgives the arrears
            
        # Recalculate final net based on waivers
        deposit_held = Decimal(settlement["deposit_held"])
        net_refund = deposit_held - total_penalties - arrears
        
        # 2. Handle Financial Execution
        if net_refund > 0:
            # Tenant gets money back. Create a refund request.
            RefundService.create_refund_request(
                tenancy=tenancy,
                amount=net_refund,
                reason=f"Lease termination refund (Penalties: {total_penalties}, Arrears: {arrears})",
                requested_by_user=approved_by_user
            )
        elif net_refund < 0:
            # Tenant owes money. 
            # TODO: Trigger InvoiceService here to generate a final invoice for the remaining balance.
            logger.warning(f"Tenant {tenancy.tenant.email} owes {abs(net_refund)} after termination.")
            
        # 3. Execute the actual termination (Archives to history, marks terminated, releases unit)
        TerminationService.execute_termination(
            termination_record=termination_record,
            approved_by=approved_by_user,
            auto_release_unit=True
        )
        
        # 4. Clear the arrears record since the tenancy is officially closed
        if hasattr(tenancy, 'arrears_record') and tenancy.arrears_record:
            tenancy.arrears_record.total_outstanding = Decimal("0.00")
            tenancy.arrears_record.status = "current" # Reset status since debt is settled
            tenancy.arrears_record.save(update_fields=['total_outstanding', 'status'])
        
        return {"status": "vacated", "settlement": settlement}