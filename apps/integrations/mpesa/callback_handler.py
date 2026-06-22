# integrations/mpesa/callback_handler.py
import logging
from ..models import WebhookEvent

logger = logging.getLogger(__name__)

class MpesaCallbackHandler:
    @staticmethod
    def process_stk_callback(callback_data: dict) -> dict:
        if callback_data.get("ResultCode") != 0:
            return {"status": "failed", "reason": callback_data.get("ResultDesc")}
            
        body = callback_data.get("Body", {}).get("stkCallback", {})
        metadata = {item["Name"]: item["Value"] for item in body.get("CallbackMetadata", {}).get("Item", [])}
        
        return {
            "transaction_id": metadata.get("MpesaReceiptNumber"),
            "phone": metadata.get("PhoneNumber"),
            "amount": metadata.get("Amount"),
            "account_ref": body.get("CheckoutRequestID"),
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