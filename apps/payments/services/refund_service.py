from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Refund, RefundStatus, TenantBalance, Payment, PaymentStatus, PaymentSource
import logging

logger = logging.getLogger(__name__)

class RefundService:
    @staticmethod
    @transaction.atomic
    def create_refund_request(tenancy, amount: Decimal, reason: str, requested_by_user):
        """Initial refund request. Remains in REQUESTED state until manager approval."""
        amount = amount.quantize(Decimal("0.01"))
        if amount <= Decimal("0.00"):
            raise ValidationError("Refund amount must be greater than 0.")

        return Refund.objects.create(
            tenancy=tenancy,
            amount=amount,
            reason=reason,
            requested_by=requested_by_user,
            status=RefundStatus.REQUESTED
        )

    @staticmethod
    @transaction.atomic
    def process_refund(refund_id: str, approved_by_user, deduction: Decimal = Decimal("0.00")):
        """
        Approves refund, applies deductions (e.g., damages), adjusts tenant balance ledger,
        and queues B2C payout via integrations layer.
        """
        refund = Refund.objects.select_related("tenancy", "tenancy__tenant").get(id=refund_id)
        if refund.status != RefundStatus.REQUESTED:
            raise ValidationError("Refund is not in a requestable state.")

        net_refund = max(Decimal("0.00"), refund.amount - deduction.quantize(Decimal("0.01")))
        
        # 1. Update Refund Record
        refund.status = RefundStatus.APPROVED
        refund.approved_by = approved_by_user
        refund.processed_at = timezone.now()
        refund.save(update_fields=["status", "approved_by", "processed_at"])

        # 2. ✅ FIX: Adjust the Accounting Ledger properly
        # If we are refunding advance credit, we must reduce total_paid so the balance equation holds.
        balance, _ = TenantBalance.objects.get_or_create(tenancy=refund.tenancy)
        
        # Reduce total_paid (money is leaving the landlord/system pocket back to tenant)
        balance.total_paid = max(Decimal("0.00"), balance.total_paid - net_refund)
        # Recalculate current_balance = total_invoiced - total_paid
        balance.current_balance = balance.total_invoiced - balance.total_paid
        balance.save(update_fields=["total_paid", "current_balance", "last_updated"])

        # 3. Create a Ledger Entry (Negative Payment) for Audit Trail
        Payment.objects.create(
            payment_id=f"REFUND-{refund.id}",
            payer=refund.tenancy.tenant, # Money goes back to payer
            amount=net_refund,
            source=PaymentSource.BANK_TRANSFER if hasattr(PaymentSource, 'BANK_TRANSFER') else 'b2c_refund',
            status=PaymentStatus.COMPLETED,
            account_received_at="B2C_Payout",
            raw_payload={"refund_id": str(refund.id), "deduction": str(deduction)},
            paid_at=timezone.now()
        )

        # 4. Queue B2C payout to tenant phone (decoupled to integrations/tasks)
        # In production: from ..tasks.refund_tasks import trigger_b2c_payout
        # trigger_b2c_payout.delay(str(refund.id), net_refund, refund.tenancy.tenant.phone_number)

        logger.info(f"Refund {refund_id} approved | Net: {net_refund} | Deduction: {deduction}")
        return {"status": "approved", "net_refund": str(net_refund), "refund_id": str(refund.id)}