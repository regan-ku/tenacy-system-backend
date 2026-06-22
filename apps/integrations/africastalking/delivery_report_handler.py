import logging
from ..models import MessageLog, WebhookEvent
from ..services.integration_logger import IntegrationLogger

logger = logging.getLogger(__name__)

class DeliveryReportHandler:
    @staticmethod
    def process_report(payload: dict) -> dict:
        """
        Updates MessageLog status based on AT delivery callback.
        Uses WebhookEvent for idempotent processing.
        """
        message_id = payload.get("id")
        status = payload.get("status")
        log_id = IntegrationLogger.log_request("africastalking_dr", "/messaging/reports", payload)

        if not message_id:
            IntegrationLogger.log_failure(log_id, "Missing message_id in delivery report")
            return {"status": "ignored", "reason": "no_message_id"}

        try:
            log_entry = MessageLog.objects.filter(external_ref=message_id).first()
            if log_entry:
                old_status = log_entry.status
                log_entry.status = status
                if status == "Delivered":
                    from django.utils import timezone
                    log_entry.delivered_at = timezone.now()
                log_entry.save(update_fields=["status", "delivered_at"])
                
                IntegrationLogger.log_response(log_id, 200, {"updated": True}, "success")
                return {"status": "updated", "old": old_status, "new": status}
            else:
                IntegrationLogger.log_response(log_id, 200, {"found": False}, "success")
                return {"status": "not_found", "message_id": message_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            return {"status": "failed", "error": str(e)}

    @staticmethod
    def queue_delivery_event(payload: dict):
        WebhookEvent.objects.create(
            source="africastalking",
            event_type="sms_delivery_report",
            payload=payload,
            processed=False
        )