from celery import shared_task
import logging
from django.utils import timezone
from django.core.cache import cache
from ..services.billing_service import BillingService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_daily_billing_cycle(self, target_date=None):
    """
    Periodic task: Runs DAILY via Celery Beat.
    Checks all active tenancies and generates recurring rent invoices ONLY for those 
    whose `next_billing_date` is today or in the past (respects advance payments).
    
    ✅ PRODUCTION SAFEGUARD: Uses a cache lock to prevent overlapping executions 
    if Celery Beat misfires or multiple workers pick up the task simultaneously.
    """
    run_date = target_date or timezone.now().date()
    lock_id = f"daily-billing-lock-{run_date}"
    
    # Acquire lock (expires in 1 hour to prevent deadlocks)
    have_lock = cache.add(lock_id, "true", 3600)
    if not have_lock:
        logger.info(f"Billing cycle already running for {run_date}. Skipping duplicate execution.")
        return {"status": "skipped", "reason": "Already running"}

    try:
        logger.info(f"Starting daily billing cycle scan for {run_date}")
        
        result = BillingService.generate_recurring_invoices(target_date=run_date)
        
        logger.info(f"Billing cycle completed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"Billing cycle failed: {str(e)}")
        self.retry(exc=e)
    finally:
        # Release lock upon completion or failure
        cache.delete(lock_id)