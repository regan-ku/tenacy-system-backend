from typing import Dict, Any, Optional
from django.conf import settings
from .channel_selector import ChannelSelector
from .integration_logger import IntegrationLogger
from .retry_service import RetryService
import logging

logger = logging.getLogger(__name__)

class NotificationRouter:
    @staticmethod
    def route_and_dispatch(
        recipient_id: str,
        message: str,
        message_type: str = "transactional",
        urgency: str = "normal",
        user_prefs: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Selects channel, logs intent, and triggers async dispatch to provider.
        Returns dispatch status & tracking ID.
        """
        # 1. Select optimal channel
        channel = ChannelSelector.select_channel(message_type, urgency, user_prefs)
        
        # 2. Log dispatch intent
        log_id = IntegrationLogger.log_request(
            provider=channel,
            endpoint=f"/dispatch/{channel}",
            request_payload={"recipient": recipient_id, "type": message_type, "message_length": len(message)},
            triggered_by_id=metadata.get("triggered_by") if metadata else None
        )

        # 3. Async dispatch mapping (placeholders for actual provider calls)
        dispatch_map = {
            "sms": "integrations.africastalking.sms_service.send_sms.delay",
            "whatsapp": "integrations.whatsapp.whatsapp_service.send_template.delay",
            "email": "integrations.services.email_dispatch.delay",
            "in_app": "communications.tasks.create_in_app.delay"
        }

        task_path = dispatch_map.get(channel)
        if not task_path:
            return {"status": "failed", "error": f"Unsupported channel: {channel}", "log_id": log_id}

        # 4. Trigger async task (in production, imported dynamically to avoid circular imports)
        try:
            from celery import current_app
            task_func = current_app.tasks[task_path]
            task_func.apply_async(args=[recipient_id, message, log_id])
            return {"status": "queued", "channel": channel, "log_id": log_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            RetryService.schedule_retry_task(task_func, recipient_id, message, log_id=log_id)
            return {"status": "retry_scheduled", "log_id": log_id}