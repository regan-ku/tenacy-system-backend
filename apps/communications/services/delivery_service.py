from typing import Dict, Any
from django.utils import timezone
from ..models import Message, DeliveryLog
import logging

logger = logging.getLogger(__name__)

class DeliveryService:
    @staticmethod
    def log_attempt(message: Message, provider: str, status: str, response_code: int = None, error: str = None, raw_response: dict = None):
        return DeliveryLog.objects.create(
            message=message,
            provider=provider,
            status=status,
            response_code=response_code,
            error_message=error,
            raw_response=raw_response or {}
        )

    @staticmethod
    def update_message_status(message: Message, status: str):
        old_status = message.status
        message.status = status
        if status in ["sent", "delivered", "failed"]:
            message.sent_at = message.sent_at or timezone.now()
        if status == "delivered":
            message.delivered_at = timezone.now()
        message.save(update_fields=["status", "sent_at", "delivered_at"])
        logger.info(f"Message {message.id[:8]} status: {old_status} → {status}")

    @staticmethod
    def dispatch_to_provider(message: Message, channel: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decouples from actual HTTP calls. Triggers Celery task that delegates to integrations/.
        Keeps this layer strictly orchestration-focused.
        """
        from ..tasks.messaging_tasks import dispatch_message_task
        log = DeliveryService.log_attempt(message, provider=channel, status="queued")
        dispatch_message_task.delay(str(message.id), channel, payload)
        return {"status": "queued", "log_id": str(log.id)}