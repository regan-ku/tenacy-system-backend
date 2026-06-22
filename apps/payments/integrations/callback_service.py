from typing import Dict, Any
from ..services.payment_service import PaymentService
from ..services.allocation_service import AllocationService
import logging

logger = logging.getLogger(__name__)

class PaymentCallbackProcessor:
    @staticmethod
    def process_inbound(provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry for all provider callbacks.
        Routes to correct parser, records payment, triggers atomic allocation.
        """
        if provider == "mpesa":
            return PaymentCallbackProcessor._handle_mpesa(payload)
        elif provider == "bank" or provider == "card":
            return {"status": "pending", "reason": "Provider integration in progress"}
            
        return {"status": "ignored", "reason": "Unsupported provider"}

    @staticmethod
    def _handle_mpesa(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts standard fields and delegates to idempotent payment recorder."""
        trans_id = payload.get("MpesaReceiptNumber") or payload.get("transaction_id")
        amount = payload.get("TransactionAmount") or payload.get("amount")
        account_ref = payload.get("AccountReference") or payload.get("account_ref")
        
        if not trans_id or not amount:
            logger.warning(f"Incomplete M-Pesa callback payload: {payload}")
            return {"status": "ignored", "reason": "Missing required callback fields"}

        # Record & allocate atomically
        result = PaymentService.record_payment(
            payment_id=trans_id,
            amount=amount,
            source="mpesa",
            account_ref=account_ref,
            raw_payload=payload
        )

        logger.info(f"M-Pesa callback processed | TXN: {trans_id} | Status: {result.get('status')}")
        return result