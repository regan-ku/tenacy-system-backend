import logging
from ..models import WebhookEvent

logger = logging.getLogger(__name__)

class MpesaCallbackHandler:
    @staticmethod
    def process_stk_callback(callback_data: dict) -> dict:
        # 1. Check if payment was successful (0 = Success)
        if callback_data.get("ResultCode") != 0:
            return {
                "status": "failed", 
                "reason": callback_data.get("ResultDesc", "Unknown error")
            }
            
        body = callback_data.get("Body", {}).get("stkCallback", {})
        
        # 2. Parse the metadata array into a clean dictionary
        metadata = {}
        for item in body.get("CallbackMetadata", {}).get("Item", []):
            metadata[item["Name"]] = item.get("Value")
        
        # 3. Return the EXACT fields PaymentService expects
        return {
            "transaction_id": metadata.get("MpesaReceiptNumber"),
            "phone": str(metadata.get("PhoneNumber", "")),
            "amount": metadata.get("Amount"),
            "account_ref": metadata.get("AccountReference"), # ✅ CRITICAL FIX: Get the Invoice/Tenancy ID we sent
            "status": "completed"
        }

    @staticmethod
    def queue_webhook_event(source: str, payload: dict):
        WebhookEvent.objects.create(
            source=source,
            event_type="mpesa_payment",
            payload=payload,
            processed=False
        )
        logger.info(f"Queued M-Pesa webhook event for async processing")