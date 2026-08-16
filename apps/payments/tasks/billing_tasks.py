from celery import shared_task
import logging
from django.utils import timezone
from ..services.billing_service import BillingService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_daily_billing_cycle(self, target_date=None):
    """
    Periodic task: Runs DAILY via Celery Beat.
    Checks all active tenancies and generates recurring rent invoices ONLY for those 
    whose `next_billing_date` is today or in the past (respects advance payments).
    """
    try:
        run_date = target_date or timezone.now().date()
        logger.info(f"Starting daily billing cycle scan for {run_date}")
        
        result = BillingService.generate_recurring_invoices(target_date=run_date)
        
        logger.info(f"Billing cycle completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Billing cycle failed: {str(e)}")
        self.retry(exc=e)