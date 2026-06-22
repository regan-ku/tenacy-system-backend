from typing import Dict, Any
from django.db import transaction
from ..models import Message, MessageStatus
from .template_service import TemplateService
from .routing_service import RoutingService
from .delivery_service import DeliveryService
import logging

logger = logging.getLogger(__name__)

class MessagingService:
    @staticmethod
    @transaction.atomic
    def create_and_dispatch(recipient_id: str, template_id: str = None, context: dict = None,
                            message_type: str = "transactional", channel_override: str = None,
                            metadata: dict = None):
        # 1. Build payload
        if template_id:
            payload = TemplateService.validate_and_prepare(template_id, context or {})
            content = payload["body"]
            channel = channel_override or payload["channel"]
        else:
            content = context.get("content", "")
            channel = channel_override or RoutingService.resolve_channel(message_type)

        # 2. Create auditable Message record
        message = Message.objects.create(
            recipient_id=recipient_id,
            channel=channel,
            message_type=message_type,
            content=content,
            status=MessageStatus.QUEUED,
            metadata=metadata or {}
        )

        # 3. Dispatch to async provider layer
        delivery_result = DeliveryService.dispatch_to_provider(message, channel, {"content": content})
        return {"message_id": str(message.id), "status": delivery_result["status"], "channel": channel}