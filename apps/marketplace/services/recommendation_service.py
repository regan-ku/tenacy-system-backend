from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from ..models import ListingView, SearchHistory, Listing

class RecommendationService:
    """
    Handles trending listings, similar properties, and personalized recommendations.
    """

    @staticmethod
    def get_trending_listings(limit: int = 6, days: int = 7):
        """
        Returns the most viewed active listings in the last X days.
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        trending_ids = ListingView.objects.filter(
            viewed_at__gte=cutoff_date,
            listing__status='active',
            listing__property__is_active=True,
            listing__property__publication__is_published=True,
            listing__property__publication__visibility_status='visible'
        ).values('listing_id').annotate(
            view_count=Count('listing_id')
        ).order_by('-view_count')[:limit]
        
        listing_ids = [item['listing_id'] for item in trending_ids]
        return Listing.objects.filter(id__in=listing_ids).select_related('property', 'property__location')

    @staticmethod
    def get_similar_properties(listing: Listing, limit: int = 4):
        """
        Finds similar active properties based on location, property type, and price range.
        """
        property_obj = listing.property
        
        # Define price range (+/- 20%)
        min_price = listing.min_rent_amount * 0.8
        max_price = listing.min_rent_amount * 1.2
        
        return Listing.objects.filter(
            status='active',
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible',
            property__property_category=property_obj.property_category,
            property__location__city=property_obj.location.city,
            min_rent_amount__gte=min_price,
            min_rent_amount__lte=max_price
        ).exclude(
            id=listing.id
        ).select_related('property', 'property__location').distinct()[:limit]

    @staticmethod
    def get_personalized_recommendations(user, limit: int = 6):
        """
        Recommends properties based on the user's recent search history.
        """
        recent_searches = SearchHistory.objects.filter(user=user).order_by('-searched_at')[:5]
        
        if not recent_searches.exists():
            return RecommendationService.get_trending_listings(limit=limit)
        
        # Extract common filters from recent searches
        cities = [s.filters_applied.get('city') for s in recent_searches if s.filters_applied.get('city')]
        estates = [s.filters_applied.get('estate') for s in recent_searches if s.filters_applied.get('estate')]
        
        query = Q(status='active', property__is_active=True, property__publication__is_published=True, property__publication__visibility_status='visible')
        
        if cities:
            query &= Q(property__location__city__in=list(set(cities)))
        if estates:
            query &= Q(property__location__estate__in=list(set(estates)))
            
        return Listing.objects.filter(query).select_related('property', 'property__location').distinct()[:limit]