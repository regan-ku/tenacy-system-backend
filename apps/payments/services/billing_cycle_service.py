from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from ..models import BillingCycle

class BillingCycleService:
    @staticmethod
    def get_cycle_config(cycle_type: str) -> dict:
        """Returns cycle configuration or safe defaults."""
        try:
            cycle = BillingCycle.objects.get(cycle_type=cycle_type, is_active=True)
            return {
                "cycle_type": cycle.cycle_type,
                "billing_day": cycle.billing_day,
                "grace_period_days": cycle.grace_period_days
            }
        except BillingCycle.DoesNotExist:
            # Fallback defaults per documentation
            defaults = {"monthly": 1, "weekly": 1, "quarterly": 1, "yearly": 1}
            return {
                "cycle_type": cycle_type,
                "billing_day": defaults.get(cycle_type, 1),
                "grace_period_days": 3
            }

    @staticmethod
    def calculate_next_billing_date(current_date: datetime, cycle_type: str, billing_day: int = 1) -> datetime:
        """
        Calculates the next rent due date based on cycle type.
        Handles month-end edge cases (e.g., billing_day=31 in Feb).
        """
        current = current_date if isinstance(current_date, datetime) else datetime.combine(current_date, datetime.min.time())
        
        if cycle_type == "weekly":
            return current + timedelta(weeks=1)
        elif cycle_type == "monthly":
            return (current + relativedelta(months=1)).replace(day=min(billing_day, 28))
        elif cycle_type == "quarterly":
            return (current + relativedelta(months=3)).replace(day=min(billing_day, 28))
        elif cycle_type == "yearly":
            return (current + relativedelta(years=1)).replace(day=min(billing_day, 28))
        
        return current + relativedelta(months=1)

    @staticmethod
    def get_billing_status(due_date: datetime, grace_period_days: int = 3) -> str:
        """
        Returns: 'current', 'due', or 'overdue'
        Used by arrears tracking & dashboard KPIs.
        """
        now = timezone.now()
        grace_end = due_date + timedelta(days=grace_period_days)
        
        if now <= due_date:
            return "current"
        elif now <= grace_end:
            return "due"
        else:
            return "overdue"