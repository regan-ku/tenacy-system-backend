from django.db.models import Q, Count, Max
from ..models import Listing, SearchHistory


class MarketplaceSearchFilter:
    """
    Applies advanced filtering to marketplace listings.
    Uses ONLY real database fields from the actual models:
      - Property.property_category
      - UnitGroup.unit_type
      - Location.city / estate / county
      - Listing.min_rent_amount
    """

    @staticmethod
    def get_public_listings():
        """
        Base queryset: only publicly visible listings.
        Kept identical to your working version (this is why price filter worked).
        """
        return Listing.objects.filter(
            status='active',
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible'
        ).select_related('property', 'property__location', 'unit_group')

    @staticmethod
    def apply_filters(queryset, filters: dict):
        # 1. Location filters (real fields on Location model)
        if filters.get('city'):
            queryset = queryset.filter(property__location__city__iexact=filters['city'])
        if filters.get('estate'):
            queryset = queryset.filter(property__location__estate__iexact=filters['estate'])

        # 2. Price range (cached on Listing.min_rent_amount)
        if filters.get('min_price'):
            queryset = queryset.filter(min_rent_amount__gte=float(filters['min_price']))
        if filters.get('max_price'):
            queryset = queryset.filter(min_rent_amount__lte=float(filters['max_price']))

        # 3. Property category — exact field from Property model
        if filters.get('property_type'):
            queryset = queryset.filter(
                property__property_category=filters['property_type']
            )

        # 4. Unit type — exact field from UnitGroup model.
        #    Matches either the listing's own unit_group OR any of the property's groups.
        if filters.get('unit_type'):
            queryset = queryset.filter(
                Q(unit_group__unit_type=filters['unit_type']) |
                Q(property__unit_groups__unit_type=filters['unit_type'])
            )

        return queryset


class SearchService:
    """
    Handles advanced marketplace search, filtering, deduplication,
    and search history logging.
    """

    @staticmethod
    def search_marketplace(query: str = "", filters: dict = None, user=None, session_id: str = None):
        filters = filters or {}

        # 1. Base public listings
        queryset = MarketplaceSearchFilter.get_public_listings()

        # 2. Text search across cached Listing fields + Property fields
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(location_summary__icontains=query) |
                Q(property__title__icontains=query) |
                Q(property__location__city__icontains=query) |
                Q(property__location__estate__icontains=query) |
                Q(property__location__county__icontains=query)
            )

        # 3. Apply advanced filters
        queryset = MarketplaceSearchFilter.apply_filters(queryset, filters)

        # 4. ✅ DEDUPLICATION (respects the filters):
        #    For each property in the FILTERED results, keep only the newest listing.
        #    This removes both JOIN duplicates and multiple-listings-per-property duplicates.
        newest_listing_per_property = (
            queryset
            .values('property_id')
            .annotate(newest_id=Max('id'))
            .values('newest_id')
        )

        queryset = Listing.objects.filter(
            id__in=newest_listing_per_property
        ).select_related('property', 'property__location', 'unit_group')

        # 5. Count + limit
        results_count = queryset.count()
        results = queryset.order_by('-created_at')[:50]

        # 6. Log search history
        SearchService._log_search(query, filters, results_count, user, session_id)

        return results, results_count

    @staticmethod
    def _log_search(query: str, filters: dict, results_count: int, user, session_id: str):
        """Logs search params silently so a logging failure never breaks the UX."""
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
        """Most frequent search queries for a trending UI."""
        return SearchHistory.objects.filter(
            search_query__isnull=False
        ).exclude(
            search_query=''
        ).values('search_query').annotate(
            count=Count('search_query')
        ).order_by('-count')[:limit]