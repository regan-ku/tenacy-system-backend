from decimal import Decimal
from typing import Dict, Any
from apps.integrations.mpesa.stk_push_service import StkPushService
from apps.integrations.mpesa.callback_handler import MpesaCallbackHandler
from ..services.payment_service import PaymentService
import logging

logger = logging.getLogger(__name__)

class MpesaPaymentGateway:
    @staticmethod
    def initiate_collection(phone: str, amount: Decimal, reference: str, description: str = "Rent Collection") -> Dict[str, Any]:
        """
        Initiates STK push with payment-specific formatting.
        Reference maps to Invoice/Tenancy for callback reconciliation.
        """
        if amount <= Decimal("0.00"):
            return {"success": False, "error": "Amount must be greater than 0"}

        return StkPushService.initiate(
            phone=phone,
            amount=amount,
            account_ref=reference,
            transaction_desc=description
        )

    @staticmethod
    def process_stk_callback(callback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses M-Pesa STK result, extracts transaction details, and delegates to core recording.
        """
        parsed = MpesaCallbackHandler.process_stk_callback(callback_payload)
        
        if parsed.get("status") == "completed":
            return PaymentService.record_payment(
                payment_id=parsed["transaction_id"],
                amount=parsed["amount"],
                source="mpesa",
                account_ref=parsed.get("account_ref"),
                raw_payload=callback_payload
            )
            
        return {"status": "failed", "reason": parsed.get("reason", "Callback processing failed")}