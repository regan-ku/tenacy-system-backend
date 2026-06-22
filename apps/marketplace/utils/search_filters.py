from django.db.models import Q
from ..models import Listing, UnitGroupAvailability

class MarketplaceSearchFilter:
    """
    Applies advanced filtering to marketplace listings based on user input.
    Optimized for public discovery with minimal database hits.
    """

    @staticmethod
    def apply_filters(queryset, filters: dict):
        """
        Applies multiple filters to a Listing queryset.
        """
        # 1. Location Filters
        if filters.get('city'):
            queryset = queryset.filter(location_summary__icontains=filters['city'])
        if filters.get('estate'):
            queryset = queryset.filter(location_summary__icontains=filters['estate'])
            
        # 2. Price Range Filters
        if filters.get('min_price'):
            queryset = queryset.filter(min_rent_amount__gte=filters['min_price'])
        if filters.get('max_price'):
            queryset = queryset.filter(min_rent_amount__lte=filters['max_price'])
            
        # 3. Property & Unit Type Filters
        if filters.get('property_type'):
            queryset = queryset.filter(property__property_category=filters['property_type'])
        if filters.get('unit_type'):
            # Map frontend unit type to backend choices if necessary, or filter directly
            queryset = queryset.filter(property__unit_groups__unit_type=filters['unit_type']).distinct()
            
        # 4. Amenity Filters (Boolean checks on parent property)
        if filters.get('pets_allowed') is not None:
            queryset = queryset.filter(property__allows_pets=filters['pets_allowed'])
        if filters.get('has_parking') is not None:
            min_parking = 1 if filters['has_parking'] else 0
            queryset = queryset.filter(property__parking_spaces__gte=min_parking)
        if filters.get('has_internet') is not None:
            queryset = queryset.filter(property__has_internet=filters['has_internet'])
            
        # 5. Billing Cycle Filter
        if filters.get('billing_cycle'):
            queryset = queryset.filter(property__unit_groups__billing_cycle=filters['billing_cycle']).distinct()

        return queryset

    @staticmethod
    def get_public_listings():
        """
        Returns the base queryset of listings that are safe for public viewing.
        Enforces: Published, Visible, Active, and linked to an Active Property.
        """
        return Listing.objects.filter(
            status='active',
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible'
        ).select_related(
            'property', 
            'property__location', 
            'unit_group'
        ).prefetch_related(
            'property__media'
        )