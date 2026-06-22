from django.db.models import Q
from django.conf import settings
from ..models import Listing, SearchHistory

class MarketplaceSearchFilter:
    """
    Helper class to keep search logic clean and reusable.
    """
    @staticmethod
    def get_public_listings():
        return Listing.objects.filter(
            status='active',
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible'
        ).select_related('property', 'property__location')

    @staticmethod
    def apply_filters(queryset, filters: dict):
        if filters.get('city'):
            queryset = queryset.filter(property__location__city__iexact=filters['city'])
        if filters.get('estate'):
            queryset = queryset.filter(property__location__estate__iexact=filters['estate'])
        if filters.get('min_price'):
            queryset = queryset.filter(min_rent_amount__gte=float(filters['min_price']))
        if filters.get('max_price'):
            queryset = queryset.filter(min_rent_amount__lte=float(filters['max_price']))
        if filters.get('unit_type'):
            queryset = queryset.filter(unit__unit_type=filters['unit_type'])
        if filters.get('property_type'):
            queryset = queryset.filter(property__property_type=filters['property_type'])
        return queryset


class SearchService:
    """
    Handles advanced marketplace search, filtering, and search history logging.
    """

    @staticmethod
    def search_marketplace(query: str = "", filters: dict = None, user=None, session_id: str = None):
        """
        Executes a marketplace search with text query and advanced filters.
        """
        filters = filters or {}
        
        # 1. Get base public listings queryset
        queryset = MarketplaceSearchFilter.get_public_listings()
        
        # 2. Apply text search (using ACTUAL database fields, not serializer properties)
        if query:
            queryset = queryset.filter(
                Q(property__title__icontains=query) | 
                Q(property__location__city__icontains=query) |
                Q(property__location__estate__icontains=query)
            )
            
        # 3. Apply advanced filters (price, unit type, amenities, etc.)
        queryset = MarketplaceSearchFilter.apply_filters(queryset, filters)
        
        # 4. Execute and get count
        results_count = queryset.count()
        results = queryset[:50] # Limit for performance on broad searches
        
        # 5. Log search history for recommendations/analytics
        SearchService._log_search(query, filters, results_count, user, session_id)
        
        return results, results_count

    @staticmethod
    def _log_search(query: str, filters: dict, results_count: int, user, session_id: str):
        """
        Synchronously logs the search parameters (fails silently to not break UX).
        """
        try:
            SearchHistory.objects.create(
                user=user,
                session_id=session_id,
                search_query=query,
                filters_applied=filters,
                results_count=results_count
            )
        except Exception:
            pass

    @staticmethod
    def get_popular_searches(limit: int = 5):
        """
        Returns the most frequently searched estates/cities for trending UI.
        """
        from django.db.models import Count
        return SearchHistory.objects.filter(
            search_query__isnull=False
        ).exclude(
            search_query=''
        ).values('search_query').annotate(
            count=Count('search_query')
        ).order_by('-count')[:limit]