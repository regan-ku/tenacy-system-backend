from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def check_expiring_tenancies(self, days_threshold: int = 30):
    """
    Identifies tenancies expiring within a specific window and logs/alerts managers.
    Recommended to run daily via Celery Beat.
    """
    try:
        from ..models import Tenancy
        from ..utils.tenancy_utils import TenancyUtils
        
        cutoff_date = timezone.now().date() + timedelta(days=days_threshold)
        expiring = Tenancy.objects.filter(
            status__in=['active', 'extended'],
            end_date__lte=cutoff_date,
            end_date__gte=timezone.now().date()
        ).select_related('tenant', 'unit', 'property')
        
        count = expiring.count()
        logger.info(f"Found {count} tenancies expiring within {days_threshold} days.")
        
        # TODO: Integrate with notification service to email landlords/tenants
        return {"expiring_count": count}
    except Exception as e:
        logger.error(f"Failed to check expiring tenancies: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2)
def auto_process_natural_expiries(self):
    """
    Automatically handles tenancies that have passed their end_date without extension or termination.
    Archives to history, updates status, and releases unit to marketplace.
    """
    try:
        from ..models import Tenancy
        from ..services.termination_service import TerminationService
        
        expired_today = Tenancy.objects.filter(
            status__in=['active', 'extended'],
            end_date__lt=timezone.now().date()
        )
        
        processed_count = 0
        for tenancy in expired_today:
            try:
                with transaction.atomic():
                    TerminationService.process_natural_expiry(tenancy)
                    processed_count += 1
            except Exception as e:
                logger.warning(f"Failed to auto-expire tenancy {tenancy.id}: {e}")
                
        logger.info(f"Successfully auto-processed {processed_count} expired tenancies.")
        return {"processed": processed_count}
    except Exception as e:
        logger.error(f"Failed to process natural expiries: {e}")
        raise self.retry(exc=e, countdown=600)


@shared_task(bind=True, max_retries=2)
def sync_tenancy_occupancy_with_marketplace(self):
    """
    Safety net task: Ensures marketplace availability perfectly matches 
    actual tenancy occupancy status. Fixes any drift caused by manual DB edits.
    """
    try:
        from ..models import Tenancy, Occupancy
        from marketplace.models import Listing
        
        # Find mismatches: Tenancy says active, but Unit says available
        mismatches = Tenancy.objects.filter(
            status__in=['active', 'pending_payment', 'extended'],
            unit__status='available'
        ).select_related('unit')
        
        fixed_count = 0
        for tenancy in mismatches:
            tenancy.unit.status = 'occupied'
            tenancy.unit.save(update_fields=['status'])
            
            # Ensure marketplace listing is hidden
            Listing.objects.filter(unit=tenancy.unit).update(status='unavailable')
            fixed_count += 1
            
        logger.info(f"Fixed {fixed_count} occupancy/marketplace mismatches.")
        return {"fixed": fixed_count}
    except Exception as e:
        logger.error(f"Marketplace sync task failed: {e}")
        raise self.retry(exc=e, countdown=900)