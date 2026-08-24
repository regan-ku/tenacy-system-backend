from typing import Dict, Any
from decimal import Decimal
from ..services.payment_service import PaymentService
from ..models import Invoice
from apps.tenancy.models.tenancy import Tenancy
import logging

logger = logging.getLogger(__name__)

class PaymentCallbackProcessor:
    """
    PLATFORM COLLECTION MODEL:
    Main entry point for all inbound payment callbacks (C2B, Webhooks, etc.).
    Resolves the tenancy from the account reference, records the payment, 
    and triggers atomic allocation to the tenant's ledger.
    """

    @staticmethod
    def process_inbound(provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Routes to correct parser based on provider."""
        if provider == "mpesa":
            return PaymentCallbackProcessor._handle_mpesa(payload)
        elif provider in ["bank", "card"]:
            return {"status": "pending", "reason": "Provider integration in progress"}
            
        return {"status": "ignored", "reason": "Unsupported provider"}

    @staticmethod
    def _resolve_tenancy_from_reference(account_ref: str):
        """
        Shared logic to resolve tenancy from an account reference.
        Used when tenants manually pay via Paybill (C2B) and type the reference.
        """
        if not account_ref:
            return None
            
        tenancy = None
        try:
            # 1. Try matching Invoice Number (e.g., "INV-1024")
            invoice = Invoice.objects.get(invoice_number=account_ref)
            tenancy = invoice.tenancy
        except Invoice.DoesNotExist:
            # 2. Fallback: Try matching Tenancy ID snippet (e.g., "TEN-12345678")
            if account_ref.startswith("TEN-"):
                ten_id_snippet = account_ref.replace("TEN-", "")
                tenancy = Tenancy.objects.filter(id__startswith=ten_id_snippet).first()
                
        if not tenancy:
            logger.warning(f"Could not resolve Tenancy/Invoice from C2B account_ref: {account_ref}")
            
        return tenancy

    @staticmethod
    def _handle_mpesa(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles C2B (Direct Paybill) callbacks.
        Extracts standard fields, resolves tenancy, and delegates to idempotent payment recorder.
        """
        # C2B payloads use different keys than STK callbacks
        trans_id = payload.get("TransID") or payload.get("MpesaReceiptNumber") or payload.get("transaction_id")
        amount = payload.get("TransAmount") or payload.get("TransactionAmount") or payload.get("amount")
        account_ref = payload.get("BillRefNumber") or payload.get("AccountReference") or payload.get("account_ref")
        
        if not trans_id or not amount:
            logger.warning(f"Incomplete M-Pesa C2B callback payload: {payload}")
            return {"status": "ignored", "reason": "Missing required callback fields"}

        # ✅ Resolve tenancy from the reference the tenant typed in their M-Pesa app
        tenancy = PaymentCallbackProcessor._resolve_tenancy_from_reference(account_ref)

        # Record & allocate atomically
        result = PaymentService.record_payment(
            payment_id=trans_id,
            amount=Decimal(str(amount)),
            source="mpesa",
            account_ref=account_ref,
            tenancy=tenancy,  # ✅ Pass resolved tenancy for allocation
            raw_payload=payload
        )

        logger.info(f"M-Pesa C2B callback processed | TXN: {trans_id} | Status: {result.get('status')}")
        return result