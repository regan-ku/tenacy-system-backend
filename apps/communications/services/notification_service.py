from typing import Dict, Any
from django.db import transaction
from ..models import Notification, MessageEvent, NotificationType
from .messaging_service import MessagingService
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def create_in_app(user_id: str, title: str, body: str, notif_type: str = NotificationType.SYSTEM, action_link: str = None):
        return Notification.objects.create(
            user_id=user_id,
            title=title,
            body=body,
            type=notif_type,
            action_link=action_link
        )

    @staticmethod
    @transaction.atomic
    def process_event(event_id: str):
        """
        Consumes a queued MessageEvent, creates dashboard notification,
        and triggers external channel dispatch if template is defined.
        """
        try:
            event = MessageEvent.objects.get(id=event_id)
            if event.processed:
                return {"status": "skipped", "reason": "already_processed"}

            # 1. Create in-app dashboard notification
            NotificationService.create_in_app(
                user_id=event.target_user_id,
                title=event.event_type.replace("_", " ").title(),
                body=str(event.payload.get("message", "")),
                notif_type=NotificationType.SYSTEM,
                action_link=event.payload.get("action_link")
            )

            # 2. Trigger external messaging (SMS/WhatsApp/Email)
            template_id = event.payload.get("template_id")
            if template_id and event.target_user_id:
                MessagingService.create_and_dispatch(
                    recipient_id=event.target_user_id,
                    template_id=template_id,
                    context=event.payload,
                    message_type=event.event_type
                )

            event.processed = True
            event.save(update_fields=["processed"])
            return {"status": "processed", "event_id": str(event.id)}
        except Exception as e:
            logger.error(f"Failed to process event {event_id}: {str(e)}")
            return {"status": "failed", "error": str(e)}