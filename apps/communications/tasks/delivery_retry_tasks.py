from celery import shared_task
import logging
from django.utils import timezone
from ..models import DeliveryLog, Message, MessageStatus
from .messaging_tasks import dispatch_message_task

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

@shared_task(bind=True, max_retries=1, default_retry_delay=300)
def retry_failed_delivery(self, log_id: str) -> dict:
    """
    Checks a failed delivery log and retries the original dispatch if under the limit.
    """
    try:
        log = DeliveryLog.objects.get(id=log_id)
        message = log.message
        
        # Check if message is already in a terminal state
        if message.status in [MessageStatus.DELIVERED, MessageStatus.FAILED]:
            return {"status": "ignored", "reason": "Message already terminal"}

        if log.attempt_number >= MAX_RETRIES:
            message.status = MessageStatus.FAILED
            message.save(update_fields=["status"])
            logger.warning(f"Max retries reached for message {message.id[:8]}. Marking as FAILED.")
            return {"status": "max_retries_reached"}

        # Increment attempt
        log.attempt_number += 1
        log.status = "retrying"
        log.save(update_fields=["attempt_number", "status"])

        # Re-dispatch via main router
        dispatch_message_task.delay(
            message_id=str(message.id),
            channel=message.channel,
            payload={"content": message.content}
        )
        
        return {"status": "retried", "attempt": log.attempt_number}
    except Exception as e:
        logger.error(f"Retry task failed for log {log_id}: {str(e)}")
        self.retry(exc=e)