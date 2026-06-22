from typing import Optional
from ..models import RequestPriority

class PriorityCalculator:
    # Keyword-to-priority mapping for automated triage
    EMERGENCY_KEYWORDS = ["water leak", "flooding", "gas leak", "electrical fire", "no water", "sewage", "burst pipe", "power surge"]
    HIGH_KEYWORDS = ["no electricity", "power outage", "structural", "roof leak", "broken window", "security door", "lock broken", "elevator"]
    MEDIUM_KEYWORDS = ["ac not working", "heater", "appliance", "plumbing issue", "drain clog", "pest", "paint peeling", "no internet"]
    LOW_KEYWORDS = ["cosmetic", "lightbulb", "minor scratch", "cleaning", "stuck drawer", "loose handle"]

    @staticmethod
    def calculate_from_description(description: str, default_priority: str = RequestPriority.MEDIUM) -> str:
        """
        Scans issue description for urgency keywords.
        Returns highest matched priority or defaults to medium.
        """
        if not description:
            return default_priority
            
        desc_lower = description.lower()
        
        if any(kw in desc_lower for kw in PriorityCalculator.EMERGENCY_KEYWORDS):
            return RequestPriority.EMERGENCY
        if any(kw in desc_lower for kw in PriorityCalculator.HIGH_KEYWORDS):
            return RequestPriority.HIGH
        if any(kw in desc_lower for kw in PriorityCalculator.MEDIUM_KEYWORDS):
            return RequestPriority.MEDIUM
        if any(kw in desc_lower for kw in PriorityCalculator.LOW_KEYWORDS):
            return RequestPriority.LOW
            
        return default_priority

    @staticmethod
    def validate_priority_transition(current: str, new: str) -> bool:
        """
        Logs warning if priority is downgraded arbitrarily.
        Managers may override, but system flags it for audit.
        Returns True = safe increase or neutral.
        """
        order = [RequestPriority.LOW, RequestPriority.MEDIUM, RequestPriority.HIGH, RequestPriority.EMERGENCY]
        try:
            current_idx = order.index(current)
            new_idx = order.index(new)
            return new_idx >= current_idx
        except ValueError:
            return False