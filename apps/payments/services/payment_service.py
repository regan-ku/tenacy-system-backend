from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Payment, PaymentStatus, PaymentSource
from .allocation_service import AllocationService
import logging

logger = logging.getLogger(__name__)

class PaymentService:
    @staticmethod
    @transaction.atomic
    def record_payment(
        payment_id: str, 
        amount: Decimal, 
        source: str, 
        account_ref: str, 
        tenancy=None, 
        payer=None, 
        raw_payload: dict = None
    ):
        # 1. IDEMPOTENCY CHECK: Prevent duplicate processing
        if Payment.objects.filter(payment_id=payment_id).exists():
            logger.warning(f"Duplicate payment ignored: {payment_id}")
            return {"status": "ignored", "reason": "Duplicate payment_id"}

        # ✅ Auto-assign payer if not explicitly provided but we have a tenancy
        if not payer and tenancy:
            payer = tenancy.tenant

        # 2. Determine initial status based on source
        # Manual payments (Cash/Bank) require manager reconciliation before allocation
        manual_sources = ['cash', 'bank_transfer', 'manual', 'cheque']
        initial_status = PaymentStatus.PENDING_RECONCILIATION if source in manual_sources else PaymentStatus.PENDING

        # 3. Create the Payment Record
        payment = Payment.objects.create(
            payment_id=payment_id,
            payer=payer,
            amount=amount.quantize(Decimal("0.01")),
            source=source,
            status=initial_status,
            account_received_at=account_ref,
            raw_payload=raw_payload or {},
            paid_at=timezone.now()
        )

        # 4. Trigger allocation engine ONLY for automated sources (M-Pesa, Card, etc.)
        if tenancy and source not in manual_sources:
            try:
                AllocationService.allocate_payment_to_tenancy(payment, tenancy)
                payment.status = PaymentStatus.COMPLETED
                payment.save(update_fields=["status"])
                logger.info(f"Successfully allocated automated payment {payment_id} to tenancy {tenancy.id}")
            except Exception as e:
                logger.error(f"Allocation failed for payment {payment_id}: {str(e)}")
                raise e
        elif source in manual_sources:
            logger.info(f"Manual payment {payment_id} recorded. Awaiting manager reconciliation.")
        else:
            logger.warning(f"Payment {payment_id} recorded but NO tenancy resolved. Status remains PENDING.")

        return {"status": "recorded", "payment_id": payment_id, "amount": str(payment.amount), "requires_reconciliation": source in manual_sources}