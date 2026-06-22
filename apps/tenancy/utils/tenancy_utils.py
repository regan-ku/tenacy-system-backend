from django.utils import timezone
from datetime import timedelta

class TenancyUtils:
    """
    Reusable helper functions for tenancy date calculations, 
    status formatting, and lifecycle checks.
    """

    @staticmethod
    def get_days_remaining(end_date) -> int:
        """
        Calculates the number of days remaining in a tenancy.
        Returns negative number if already expired.
        """
        if not end_date:
            return 9999 # Indefinite tenancy
        
        today = timezone.now().date()
        delta = end_date - today
        return delta.days

    @staticmethod
    def is_expiring_soon(end_date, days_threshold: int = 30) -> bool:
        """
        Checks if a tenancy is expiring within a specified threshold.
        """
        days_remaining = TenancyUtils.get_days_remaining(end_date)
        return 0 <= days_remaining <= days_threshold

    @staticmethod
    def is_currently_active(status: str) -> bool:
        """
        Validates if a given status string represents an active occupancy state.
        """
        active_statuses = ['pending_payment', 'active', 'extended']
        return status in active_statuses

    @staticmethod
    def calculate_grace_period_end(billing_date: int, grace_days: int = 3) -> int:
        """
        Calculates the absolute deadline day of the month for payments.
        """
        deadline = billing_date + grace_days
        # Handle month rollover (e.g., billing on 28th + 5 days = 33 -> 3rd of next month)
        return deadline if deadline <= 31 else deadline - 31