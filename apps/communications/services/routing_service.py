from typing import Dict, Any, Optional
from ..models.message_template import Channel
import logging

logger = logging.getLogger(__name__)

class RoutingService:
    CHANNEL_PRIORITY = {
        "urgent": [Channel.SMS, Channel.WHATSAPP, Channel.EMAIL],
        "transactional": [Channel.IN_APP, Channel.WHATSAPP, Channel.SMS],
        "reminder": [Channel.SMS, Channel.WHATSAPP, Channel.EMAIL],
        "campaign": [Channel.WHATSAPP, Channel.SMS],
        "system": [Channel.IN_APP, Channel.EMAIL]
    }

    @classmethod
    def resolve_channel(cls, message_type: str, urgency: str = "normal", user_prefs: Optional[Dict] = None) -> str:
        """Returns single optimal channel string based on type & priority"""
        base_type = message_type.split("_")[0]
        candidates = cls.CHANNEL_PRIORITY.get(urgency, cls.CHANNEL_PRIORITY.get(base_type, [Channel.IN_APP]))

        if user_prefs and user_prefs.get("preferred_channel") in candidates:
            return user_prefs["preferred_channel"]
        return candidates[0]