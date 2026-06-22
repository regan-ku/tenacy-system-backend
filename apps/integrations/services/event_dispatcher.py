from typing import Dict, Any
from .notification_router import NotificationRouter
import logging

logger = logging.getLogger(__name__)

class EventDispatcher:
    """
    Decouples system events from integration execution.
    Used by Django signals or service layer callbacks.
    """
    EVENT_MAP = {
        "tenancy.created": {"type": "transactional", "urgency": "high", "template": "welcome_tenancy"},
        "tenancy.terminated": {"type": "transactional", "urgency": "normal", "template": "tenancy_ended"},
        "payment.received": {"type": "transactional", "urgency": "normal", "template": "payment_confirm"},
        "invoice.overdue": {"type": "reminder", "urgency": "urgent", "template": "rent_reminder"},
        "application.approved": {"type": "transactional", "urgency": "high", "template": "app_approved"},
        "application.rejected": {"type": "transactional", "urgency": "normal", "template": "app_rejected"},
        "maintenance.assigned": {"type": "system", "urgency": "normal", "template": "task_assigned"},
    }

    @classmethod
    def dispatch_event(cls, event_name: str, recipient_id: str, context: Dict[str, Any]):
        """Triggers notification routing based on predefined event map"""
        config = cls.EVENT_MAP.get(event_name)
        if not config:
            logger.warning(f"No integration route mapped for event: {event_name}")
            return {"status": "ignored", "reason": "unmapped_event"}

        message = context.get("message", f"System notification: {event_name}")
        
        return NotificationRouter.route_and_dispatch(
            recipient_id=recipient_id,
            message=message,
            message_type=config["type"],
            urgency=config["urgency"],
            metadata={"event": event_name, "triggered_by": context.get("triggered_by")}
        )