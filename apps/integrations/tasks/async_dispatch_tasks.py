from celery import shared_task
import logging
from django.db import transaction
from ..models import WebhookEvent
from ..services.integration_logger import IntegrationLogger

# Import Services & Handlers (Deferred imports to avoid circular deps if any)
from ..africastalking.sms_service import SmsService
from ..whatsapp.whatsapp_service import WhatsAppService
from ..mpesa.callback_handler import MpesaCallbackHandler

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_sms_task(self, log_id: str, phone: str, message: str, sender_id: str = "Tennacy") -> dict:
    """
    Celery task wrapper for sending SMS.
    Handles Celery-level retries if the service call fails unexpectedly.
    """
    try:
        result = SmsService.send_single(phone, message, sender_id)
        if not result.get("success"):
            # If service fails (e.g. network), retry via Celery
            raise Exception(result.get("error", "Unknown SMS dispatch failure"))
        return result
    except Exception as e:
        IntegrationLogger.log_failure(log_id, str(e))
        logger.error(f"SMS Task Failed (Attempt {self.request.retries + 1}): {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_whatsapp_task(self, log_id: str, phone: str, template_name: str, language_code: str = "en", components: list = None) -> dict:
    """
    Celery task wrapper for sending WhatsApp messages.
    """
    try:
        result = WhatsAppService.send_template(phone, template_name, language_code, components)
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown WhatsApp dispatch failure"))
        return result
    except Exception as e:
        IntegrationLogger.log_failure(log_id, str(e))
        logger.error(f"WhatsApp Task Failed (Attempt {self.request.retries + 1}): {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def process_webhook_queue(self, limit: int = 50):
    """
    Periodic task: Fetches unprocessed WebhookEvents and routes them to appropriate handlers.
    Ensures idempotent processing of provider callbacks.
    """
    try:
        events = WebhookEvent.objects.filter(processed=False).order_by("created_at")[:limit]
        processed_count = 0

        for event in events:
            try:
                with transaction.atomic():
                    # Refresh to ensure we don't process a claim made by another worker
                    event.refresh_from_db()
                    if event.processed:
                        continue

                    source = event.source
                    payload = event.payload
                    
                    # Route to specific handlers
                    if source == "mpesa_stk":
                        MpesaCallbackHandler.process_stk_callback(payload)
                    elif source == "africastalking_delivery":
                        from ..africastalking.delivery_report_handler import DeliveryReportHandler
                        DeliveryReportHandler.process_report(payload)
                    elif source == "whatsapp_inbound":
                        from ..whatsapp.webhook_handler import WhatsAppWebhookHandler
                        WhatsAppWebhookHandler.queue_inbound_message(payload)
                    
                    # Mark as processed
                    event.processed = True
                    event.save(update_fields=["processed"])
                    processed_count += 1

            except Exception as e:
                logger.error(f"Failed to process event {event.id}: {str(e)}")
                # Do not retry individual event; let it sit for manual inspection or next run
        
        return f"Processed {processed_count} webhook events"

    except Exception as e:
        logger.error(f"Webhook Queue Task Failed: {str(e)}")
        self.retry(exc=e)