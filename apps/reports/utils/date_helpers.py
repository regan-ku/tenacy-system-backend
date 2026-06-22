from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class DateHelperUtils:
    """
    Standardized date range generation for common reporting periods.
    Ensures all reports use the exact same time boundaries.
    """

    @staticmethod
    def get_current_month_range():
        """Returns start and end datetime for the current calendar month."""
        now = timezone.now()
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Last day of current month
        next_month = now.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date

    @staticmethod
    def get_current_quarter_range():
        """Returns start and end datetime for the current calendar quarter."""
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        start_date = datetime(now.year, 3 * quarter - 2, 1, tzinfo=timezone.get_current_timezone())
        
        # End of quarter
        if quarter == 4:
            end_date = datetime(now.year, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.get_current_timezone())
        else:
            end_date = datetime(now.year, 3 * quarter + 1, 1, tzinfo=timezone.get_current_timezone()) - timedelta(microseconds=1)
            
        return start_date, end_date

    @staticmethod
    def get_custom_range(days: int = 30):
        """Returns start and end datetime for the last N days."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date

    @staticmethod
    def get_previous_period_comparison(start_date, end_date):
        """
        Given a date range, returns the exact same duration for the previous period.
        Useful for period-over-period growth calculations.
        """
        duration = end_date - start_date
        prev_end = start_date - timedelta(microseconds=1)
        prev_start = prev_end - duration
        return prev_start, prev_end