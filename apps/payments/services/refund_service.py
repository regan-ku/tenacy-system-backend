from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Refund, RefundStatus, TenantBalance
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
        Approves refund, applies deductions (e.g., damages), adjusts tenant balance,
        and queues B2C payout via integrations layer.
        """
        refund = Refund.objects.select_related("tenancy", "tenancy__tenant").get(id=refund_id)
        if refund.status != RefundStatus.REQUESTED:
            raise ValidationError("Refund is not in a requestable state.")

        net_refund = max(Decimal("0.00"), refund.amount - deduction.quantize(Decimal("0.01")))
        
        refund.status = RefundStatus.APPROVED
        refund.approved_by = approved_by_user
        refund.processed_at = timezone.now()
        refund.save(update_fields=["status", "approved_by", "processed_at"])

        # Update tenant running balance (credit removed since it's being returned)
        balance = refund.tenancy.balance_record
        balance.current_balance -= net_refund
        balance.save(update_fields=["current_balance"])

        # Queue B2C payout to tenant/landlord phone (decoupled to integrations/tasks)
        # In production: from ..tasks.refund_tasks import trigger_b2c_payout
        # trigger_b2c_payout.delay(str(refund.id), net_refund, refund.tenancy.tenant.phone_number)

        logger.info(f"Refund {refund_id} approved | Net: {net_refund} | Deduction: {deduction}")
        return {"status": "approved", "net_refund": str(net_refund), "refund_id": str(refund.id)}