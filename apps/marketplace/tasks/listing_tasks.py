from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def auto_archive_stale_listings(self, days_inactive: int = 90):
    """
    Automatically archives listings that have been 'unavailable' or 'hidden' 
    for an extended period to keep the active database lean and improve search performance.
    Recommended to run daily via Celery Beat.
    """
    try:
        from ..models import Listing
        
        cutoff_date = timezone.now() - timedelta(days=days_inactive)
        
        archived_count = Listing.objects.filter(
            status__in=['unavailable', 'hidden'],
            updated_at__lt=cutoff_date
        ).update(status='archived')
        
        logger.info(f"Automatically archived {archived_count} stale marketplace listings.")
        return archived_count
        
    except Exception as e:
        logger.error(f"Failed to auto-archive stale listings: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_listing_visibility_with_availability(self, unit_group_id: int):
    """
    Ensures that a listing's marketplace status perfectly matches its 
    underlying UnitGroupAvailability. If available_units == 0, listing becomes 'unavailable'.
    Triggered by the AvailabilityService when tenancy changes occur.
    """
    try:
        from ..models import Listing, UnitGroupAvailability
        
        availability = UnitGroupAvailability.objects.filter(unit_group_id=unit_group_id).first()
        if not availability:
            return False
            
        target_status = 'active' if availability.is_marketplace_visible else 'unavailable'
        
        updated_count = Listing.objects.filter(
            unit_group_id=unit_group_id
        ).exclude(status=target_status).update(status=target_status)
        
        if updated_count > 0:
            logger.info(f"Synced {updated_count} listings to status '{target_status}' for unit group {unit_group_id}.")
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync listing visibility for unit group {unit_group_id}: {e}")
        raise self.retry(exc=e, countdown=60)