import logging
from django.utils import timezone
from ..models import MessageLog, WebhookEvent
from ..services.integration_logger import IntegrationLogger
from ..utils.signature_validator import verify_webhook_signature

logger = logging.getLogger(__name__)

class WhatsAppWebhookHandler:
    @staticmethod
    def verify_inbound_signature(request_body: bytes, signature_header: str) -> bool:
        from django.conf import settings
        secret = settings.WHATSAPP_APP_SECRET_ENCRYPTED # In prod, decrypt before verify
        return verify_webhook_signature(request_body, signature_header, secret, "sha256")

    @staticmethod
    def process_status_update(payload: dict) -> dict:
        statuses = payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("statuses", [])
        results = []
        
        for status in statuses:
            msg_id = status.get("id")
            new_status = status.get("status")
            log_id = IntegrationLogger.log_request("whatsapp_status", "/webhook/status", {"id": msg_id, "status": new_status})
            
            try:
                log_entry = MessageLog.objects.filter(external_ref=msg_id).first()
                if log_entry:
                    old_status = log_entry.status
                    log_entry.status = new_status
                    if new_status in ["delivered", "read"]:
                        log_entry.delivered_at = timezone.now()
                    log_entry.save(update_fields=["status", "delivered_at"])
                    IntegrationLogger.log_response(log_id, 200, {"updated": True}, "success")
                    results.append({"id": msg_id, "status": new_status})
            except Exception as e:
                IntegrationLogger.log_failure(log_id, str(e))
                results.append({"id": msg_id, "status": "failed", "error": str(e)})
                
        return {"processed": len(results), "results": results}

    @staticmethod
    def queue_inbound_message(payload: dict):
        WebhookEvent.objects.create(
            source="whatsapp",
            event_type="inbound_message",
            payload=payload,
            processed=False
        )