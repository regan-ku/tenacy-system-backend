from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from ..models import FeaturedListing, Listing

class FeaturedListingService:
    """
    Manages premium placements, homepage hero banners, and sponsored property logic.
    """

    @staticmethod
    @transaction.atomic
    def feature_listing(listing: Listing, placement: str, priority: int = 0, duration_days: int = 30) -> FeaturedListing:
        """
        Promotes a listing to a featured placement for a specified duration.
        """
        if not listing.status == 'active':
            raise ValidationError("Cannot feature an inactive or unavailable listing.")

        end_date = timezone.now() + timezone.timedelta(days=duration_days)
        
        featured, created = FeaturedListing.objects.update_or_create(
            listing=listing,
            placement=placement,
            defaults={
                'is_active': True,
                'start_date': timezone.now(),
                'end_date': end_date,
                'priority': priority
            }
        )
        return featured

    @staticmethod
    @transaction.atomic
    def remove_featured_status(listing: Listing, placement: str = None):
        """
        Removes featured status from a listing.
        """
        filters = {'listing': listing, 'is_active': True}
        if placement:
            filters['placement'] = placement
            
        FeaturedListing.objects.filter(**filters).update(is_active=False)

    @staticmethod
    def get_active_featured_listings(placement: str = None, limit: int = 10):
        """
        Retrieves currently active featured listings for homepage or category displays.
        """
        now = timezone.now()
        filters = {
            'is_active': True,
            'start_date__lte': now,
        }
        # Handle nullable end_date (indefinite) or future end_date
        from django.db.models import Q
        filters['end_date__gte'] = now
        filters['end_date__isnull'] = True # Or use Q(end_date__gte=now) | Q(end_date__isnull=True)
        
        queryset = FeaturedListing.objects.filter(
            Q(end_date__gte=now) | Q(end_date__isnull=True),
            is_active=True,
            start_date__lte=now,
            listing__status='active',
            listing__property__is_active=True,
            listing__property__publication__is_published=True,
            listing__property__publication__visibility_status='visible'
        ).select_related('listing', 'listing__property', 'listing__property__location')

        if placement:
            queryset = queryset.filter(placement=placement)
            
        return queryset.order_by('-priority', '-start_date')[:limit]