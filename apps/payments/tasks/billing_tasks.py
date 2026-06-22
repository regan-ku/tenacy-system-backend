from celery import shared_task
import logging
from django.utils import timezone
from ..services.billing_service import BillingService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_monthly_billing_cycle(self, target_date=None):
    """
    Periodic task: Generates recurring rent invoices for all active tenancies.
    Typically scheduled via Celery Beat on the 1st of each month.
    """
    try:
        run_date = target_date or timezone.now().date()
        logger.info(f"Starting billing cycle for {run_date}")
        result = BillingService.generate_recurring_invoices(target_date=run_date)
        logger.info(f"Billing cycle completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Billing cycle failed: {str(e)}")
        self.retry(exc=e)