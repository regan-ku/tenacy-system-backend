from celery import shared_task
import logging
from django.db.models import Q
from apps.tenancy.models import Tenancy  # ✅ FIXED: Import from tenancy app
from ..services.arrears_service import ArrearsService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def update_all_tenancy_arrears(self):
    """
    Daily safety sweep: Scans tenancies with open invoices, recalculates 
    outstanding balances, and updates arrears records/statuses.
    """
    try:
        logger.info("Starting daily arrears update scan")
        
        # ✅ OPTIMIZATION: Only fetch tenancies that actually have pending/partial/overdue invoices
        # This prevents querying 10,000 fully-paid tenancies every night.
        tenancies = Tenancy.objects.filter(
            status="active",
            invoices__status__in=["pending", "partial", "overdue"]
        ).distinct()
        
        updated_count = 0
        
        for tenancy in tenancies:
            try:
                ArrearsService.update_tenancy_arrears(tenancy)
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update arrears for tenancy {tenancy.id}: {str(e)}")
                
        logger.info(f"Arrears scan completed. Updated: {updated_count} tenancies.")
        return f"Arrears scan completed. Updated: {updated_count}"
    except Exception as e:
        logger.error(f"Arrears task failed: {str(e)}")
        self.retry(exc=e)