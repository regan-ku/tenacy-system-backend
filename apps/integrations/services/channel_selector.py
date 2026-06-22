from typing import Dict, Any, Optional

class ChannelSelector:
    """
    Routes system events to the most appropriate channel based on urgency,
    message type, and fallback rules. Matches §11.4 notification routing logic.
    """
    CHANNEL_PRIORITY = {
        "urgent": ["sms", "whatsapp"],
        "transactional": ["whatsapp", "email"],
        "reminder": ["sms", "whatsapp", "email"],
        "campaign": ["whatsapp", "sms"],
        "marketing": ["email", "whatsapp"],
        "system": ["in_app", "email"]
    }

    @classmethod
    def select_channel(cls, message_type: str, urgency: str = "normal", user_prefs: Optional[Dict] = None) -> str:
        """Returns single optimal channel string"""
        # 1. Resolve base priority from type
        base_type = message_type.split("_")[0] if "_" in message_type else message_type
        candidates = cls.CHANNEL_PRIORITY.get(urgency, cls.CHANNEL_PRIORITY.get(base_type, ["sms"]))

        # 2. Apply user preference override if available
        if user_prefs and user_prefs.get("preferred_channel") in candidates:
            return user_prefs["preferred_channel"]

        # 3. Fallback to first available
        return candidates[0] if candidates else "sms"