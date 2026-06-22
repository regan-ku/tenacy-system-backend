# payments/tasks/arrears_tasks.py
from celery import shared_task
import logging
from tenancy.models import Tenancy  # ✅ FIXED: Import from tenancy app
from ..services.arrears_service import ArrearsService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def update_all_tenancy_arrears(self):
    """
    Scans all active tenancies, recalculates outstanding balances,
    and updates arrears records. Runs daily.
    """
    try:
        logger.info("Starting daily arrears update scan")
        tenancies = Tenancy.objects.filter(status="active")
        updated_count = 0
        
        for tenancy in tenancies:
            try:
                ArrearsService.update_tenancy_arrears(tenancy)
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update arrears for tenancy {tenancy.id}: {str(e)}")
                
        return f"Arrears scan completed. Updated: {updated_count}"
    except Exception as e:
        logger.error(f"Arrears task failed: {str(e)}")
        self.retry(exc=e)