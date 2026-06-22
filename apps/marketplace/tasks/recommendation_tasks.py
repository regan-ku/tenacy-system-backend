from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def update_trending_listings_cache(self, days: int = 7, limit: int = 10):
    """
    Precomputes the most viewed active listings over the last X days.
    Stores the result in Redis cache for instant API retrieval.
    Recommended to run hourly via Celery Beat.
    """
    try:
        from ..models import Listing, ListingView
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Aggregate view counts for active, visible listings
        trending_data = ListingView.objects.filter(
            viewed_at__gte=cutoff_date,
            listing__status='active',
            listing__property__is_active=True,
            listing__property__publication__is_published=True,
            listing__property__publication__visibility_status='visible'
        ).values('listing_id').annotate(
            view_count=Count('listing_id')
        ).order_by('-view_count')[:limit]
        
        listing_ids = [item['listing_id'] for item in trending_data]
        
        # TODO: Cache this list in Redis
        # Example: cache.set('marketplace_trending_listings', listing_ids, timeout=3600)
        
        logger.info(f"Updated trending listings cache with {len(listing_ids)} listings.")
        return listing_ids
        
    except Exception as e:
        logger.error(f"Failed to update trending listings cache: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2)
def refresh_similar_properties_cache(self, listing_id: int):
    """
    Precomputes similar properties for a specific listing to speed up 
    the "You might also like" section on the property detail page.
    """
    try:
        from ..models import Listing
        
        listing = Listing.objects.select_related('property', 'property__location').get(id=listing_id)
        property_obj = listing.property
        
        # Define price range (+/- 20%)
        min_price = float(listing.min_rent_amount) * 0.8 if listing.min_rent_amount else 0
        max_price = float(listing.min_rent_amount) * 1.2 if listing.min_rent_amount else float('inf')
        
        similar_ids = list(Listing.objects.filter(
            status='active',
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible',
            property__property_category=property_obj.property_category,
            property__location__city=property_obj.location.city,
            min_rent_amount__gte=min_price,
            min_rent_amount__lte=max_price
        ).exclude(id=listing.id).values_list('id', flat=True).distinct()[:4])
        
        # TODO: Cache this list in Redis
        # Example: cache.set(f'similar_listings_{listing_id}', similar_ids, timeout=86400)
        
        logger.info(f"Refreshed similar properties cache for listing {listing_id}.")
        return similar_ids
        
    except Exception as e:
        logger.error(f"Failed to refresh similar properties for listing {listing_id}: {e}")
        raise self.retry(exc=e, countdown=60)