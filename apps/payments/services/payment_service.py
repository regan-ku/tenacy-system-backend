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

        # Note: We DO NOT validate account_ref against PaymentVerificationService here.
        # account_ref is the Invoice Number. Paybill validation already happened at STK Push time.

        # ✅ Auto-assign payer if not explicitly provided but we have a tenancy
        if not payer and tenancy:
            payer = tenancy.tenant

        # 2. Create the Payment Record
        payment = Payment.objects.create(
            payment_id=payment_id,
            payer=payer,
            amount=amount.quantize(Decimal("0.01")),
            source=source,
            status=PaymentStatus.PENDING,
            account_received_at=account_ref,
            raw_payload=raw_payload or {},
            paid_at=timezone.now()
        )

        # 3. Trigger allocation engine
        if tenancy:
            try:
                AllocationService.allocate_payment_to_tenancy(payment, tenancy)
                payment.status = PaymentStatus.COMPLETED
                payment.save(update_fields=["status"])
                logger.info(f"Successfully allocated payment {payment_id} to tenancy {tenancy.id}")
            except Exception as e:
                logger.error(f"Allocation failed for payment {payment_id}: {str(e)}")
                # Keep status as PENDING so it can be manually reconciled later
                raise e
        else:
            logger.warning(f"Payment {payment_id} recorded but NO tenancy resolved. Status remains PENDING.")

        return {"status": "recorded", "payment_id": payment_id, "amount": str(payment.amount)}