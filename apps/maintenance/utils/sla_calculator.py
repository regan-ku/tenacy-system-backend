from datetime import datetime, timedelta
from typing import Optional
from ..models import RequestPriority

class SLACalculator:
    # Base SLA windows per priority (in hours) per documentation §8
    PRIORITY_SLA_MAP = {
        RequestPriority.EMERGENCY: 2,   # 2 hours
        RequestPriority.HIGH: 24,       # 24 hours
        RequestPriority.MEDIUM: 72,     # 3 days
        RequestPriority.LOW: 168,       # 7 days
    }

    @staticmethod
    def calculate_due_at(created_at: datetime, category_default_hours: Optional[int] = None, priority: str = RequestPriority.MEDIUM) -> datetime:
        """
        Calculates SLA deadline.
        Priority overrides category default if stricter.
        """
        category_hours = category_default_hours or SLACalculator.PRIORITY_SLA_MAP.get(priority, 72)
        priority_hours = SLACalculator.PRIORITY_SLA_MAP.get(priority, 72)
        
        # Use the stricter (smaller) window
        base_hours = min(category_hours, priority_hours)
        return created_at + timedelta(hours=base_hours)

    @staticmethod
    def check_status(sla_due_at: datetime, current_time: Optional[datetime] = None) -> dict:
        """
        Returns breach status + hours remaining/overdue.
        Used by escalation service & dashboard KPIs.
        """
        now = current_time or datetime.now()
        diff = (now - sla_due_at).total_seconds() / 3600
        
        if diff <= 0:
            return {"breached": False, "hours_remaining": round(abs(diff), 2)}
        return {"breached": True, "hours_overdue": round(diff, 2)}