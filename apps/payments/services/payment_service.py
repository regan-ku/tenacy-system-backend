from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Payment, PaymentStatus, PaymentSource
from .allocation_service import AllocationService
from .payment_verification_service import PaymentVerificationService

class PaymentService:
    @staticmethod
    @transaction.atomic
    def record_payment(
        payment_id: str, amount: Decimal, source: str, 
        account_ref: str, tenancy=None, payer=None, raw_payload: dict = None
    ):
        """
        Idempotent payment recording. Prevents duplicate M-Pesa/callback processing.
        """
        # 1. Duplicate check
        if Payment.objects.filter(payment_id=payment_id).exists():
            return {"status": "ignored", "reason": "Duplicate payment_id"}

        # 2. Validate routing account (if reference provided)
        if account_ref and not PaymentVerificationService.is_account_verified_and_active(account_ref):
            raise ValidationError("Payment routed to unverified account. Funds quarantined.")

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
            AllocationService.allocate_payment_to_tenancy(payment, tenancy)
            payment.status = PaymentStatus.COMPLETED
            payment.save(update_fields=["status"])

        return {"status": "recorded", "payment_id": payment_id, "amount": str(payment.amount)}

    @staticmethod
    def process_callback_payload(payload: dict):
        """
        Normalizes provider webhook → calls record_payment()
        Example: M-Pesa C2B/STK callback structure
        """
        return PaymentService.record_payment(
            payment_id=payload.get("MpesaReceiptNumber"),
            amount=Decimal(str(payload.get("TransactionAmount", 0))),
            source=PaymentSource.MPESA,
            account_ref=payload.get("BusinessShortCode"),
            tenancy_id=payload.get("AccountReference"), # Maps to tenancy code
            raw_payload=payload
        )