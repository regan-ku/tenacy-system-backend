from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
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
        # ✅ PLATFORM MODEL: Record the actual Platform Paybill shortcode for audit trails
        platform_shortcode = getattr(settings, 'MPESA_SHORT_CODE', 'Unknown')
        received_at = f"Platform Paybill ({platform_shortcode})" if source == 'mpesa' else "Platform Collection"

        payment = Payment.objects.create(
            payment_id=payment_id,
            tenancy=tenancy,                  # ✅ Links payment to the specific tenancy
            account_reference=account_ref,    # ✅ Stores the reference (e.g., "TEN-12345678") for reconciliation
            payer=payer,
            amount=amount.quantize(Decimal("0.01")),
            source=source,
            status=initial_status,
            account_received_at=received_at,  
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
                # We don't raise here to prevent the callback from failing and retrying infinitely. 
                # Instead, we leave it as PENDING for manual reconciliation.
                payment.status = PaymentStatus.PENDING_RECONCILIATION
                payment.save(update_fields=["status"])
        elif source in manual_sources:
            logger.info(f"Manual payment {payment_id} recorded. Awaiting manager reconciliation.")
        else:
            logger.warning(f"Payment {payment_id} recorded but NO tenancy resolved. Status remains PENDING.")

        return {
            "status": "recorded", 
            "payment_id": payment_id, 
            "amount": str(payment.amount), 
            "requires_reconciliation": source in manual_sources or payment.status == PaymentStatus.PENDING_RECONCILIATION
        }