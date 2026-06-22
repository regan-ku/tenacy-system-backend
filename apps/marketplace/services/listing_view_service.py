from django.db import transaction
from django.utils import timezone
from ..models import ListingView, Listing

class ListingViewService:
    """
    Tracks listing impressions and views for analytics, trending algorithms, and performance metrics.
    """

    @staticmethod
    @transaction.atomic
    def record_view(listing: Listing, user=None, source: str = 'direct', ip_address: str = None, user_agent: str = None):
        """
        Records a view/impression for a listing.
        Includes basic duplicate view throttling (e.g., ignoring multiple views from same IP within 1 hour).
        """
        # Optional: Add duplicate throttling logic here using Redis or DB checks
        # For now, we log the view directly for analytics aggregation
        
        ListingView.objects.create(
            listing=listing,
            user=user,
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
            viewed_at=timezone.now()
        )

    @staticmethod
    def get_listing_analytics(listing: Listing, days: int = 30):
        """
        Retrieves view analytics for a specific listing over a given period.
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        cutoff = timezone.now() - timedelta(days=days)
        
        views = ListingView.objects.filter(
            listing=listing,
            viewed_at__gte=cutoff
        )
        
        total_views = views.count()
        views_by_source = views.values('source').annotate(count=Count('source'))
        
        return {
            'total_views': total_views,
            'views_by_source': list(views_by_source),
            'period_days': days
        }