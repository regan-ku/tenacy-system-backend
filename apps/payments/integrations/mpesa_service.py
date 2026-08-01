from decimal import Decimal
from typing import Dict, Any
from apps.integrations.mpesa.stk_push_service import StkPushService
from apps.integrations.mpesa.callback_handler import MpesaCallbackHandler
from ..services.payment_service import PaymentService
from ..models import Invoice
from apps.tenancy.models.tenancy import Tenancy
import logging

logger = logging.getLogger(__name__)

class MpesaPaymentGateway:
    @staticmethod
    def initiate_collection(phone: str, amount: Decimal, reference: str, description: str = "Rent Collection") -> Dict[str, Any]:
        """
        Initiates STK push with payment-specific formatting.
        """
        if amount <= Decimal("0.00"):
            return {"success": False, "error": "Amount must be greater than 0"}

        # ✅ CRITICAL: Enforce Safaricom's 12-character limit for AccountReference
        if len(reference) > 12:
            logger.warning(f"Account reference {reference} exceeds 12 chars. Truncating to prevent API rejection.")
            reference = reference[:12]

        return StkPushService.initiate(
            phone=phone,
            amount=amount,
            account_ref=reference,
            transaction_desc=description
        )

    @staticmethod
    def process_stk_callback(callback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses M-Pesa STK result, resolves tenancy/invoice, and delegates to core recording.
        """
        parsed = MpesaCallbackHandler.process_stk_callback(callback_payload)
        
        if parsed.get("status") == "completed":
            account_ref = parsed.get("account_ref")
            tenancy = None
            
            # ✅ RESOLVE TENANCY FROM SHORT REFERENCE
            if account_ref:
                try:
                    # We expect account_ref to be the Invoice Number (e.g., "INV-1024")
                    invoice = Invoice.objects.get(invoice_number=account_ref)
                    tenancy = invoice.tenancy
                except Invoice.DoesNotExist:
                    # Fallback: If you passed a short Tenancy code (e.g., "TEN-12345678")
                    if account_ref.startswith("TEN-"):
                        ten_id_snippet = account_ref.replace("TEN-", "")
                        tenancy = Tenancy.objects.filter(id__startswith=ten_id_snippet).first()
                        
                    if not tenancy:
                        logger.error(f"Could not resolve Tenancy/Invoice from account_ref: {account_ref}")

            return PaymentService.record_payment(
                payment_id=parsed["transaction_id"],
                amount=Decimal(str(parsed["amount"])),
                source="mpesa",
                account_ref=account_ref,
                tenancy=tenancy, # ✅ Now correctly passing the resolved model instance
                raw_payload=callback_payload
            )
            
        return {"status": "failed", "reason": parsed.get("reason", "Callback processing failed")}