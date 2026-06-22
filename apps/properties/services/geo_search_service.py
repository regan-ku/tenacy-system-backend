from django.db.models import Q
from ..models import Unit, Location
from ..utils.geo_utils import calculate_distance

class GeoSearchService:
    """
    Handles geospatial queries for the marketplace, including 
    radius searches, nearby units, and location-based filtering.
    """

    @staticmethod
    def find_nearby_available_units(latitude: float, longitude: float, radius_km: float = 5.0) -> list:
        """
        Finds available units within a specific radius (in km) of a given coordinate.
        Uses a two-step approach: 
        1. Fast database bounding box filter.
        2. Precise Python Haversine distance calculation for final filtering.
        """
        # 1. Rough bounding box calculation (1 degree lat/lon is approx 111km)
        degree_offset = radius_km / 111.0
        
        min_lat = latitude - degree_offset
        max_lat = latitude + degree_offset
        min_lon = longitude - degree_offset
        max_lon = longitude + degree_offset

        # 2. Fast database query for units that are AVAILABLE and within the bounding box
        # We use select_related to prevent N+1 queries on the Location model
        candidate_units = Unit.objects.filter(
            status='available',
            property__is_active=True,
            property__location__latitude__gte=min_lat,
            property__location__latitude__lte=max_lat,
            property__location__longitude__gte=min_lon,
            property__location__longitude__lte=max_lon
        ).select_related('property', 'property__location', 'unit_group')

        # 3. Precise distance filtering in Python (since we aren't assuming PostGIS is installed)
        nearby_units = []
        for unit in candidate_units:
            loc = unit.property.location
            if loc.latitude and loc.longitude:
                distance = calculate_distance(
                    float(latitude), float(longitude),
                    float(loc.latitude), float(loc.longitude)
                )
                if distance <= radius_km:
                    # Attach distance to the object dynamically for frontend display
                    unit.distance_km = round(distance, 2)
                    nearby_units.append(unit)

        # Sort by distance (closest first)
        return sorted(nearby_units, key=lambda x: x.distance_km)

    @staticmethod
    def search_by_location_keywords(keyword: str) -> list:
        """
        Searches for available units based on normalized location keywords 
        (e.g., estate, street, city, county, landmark).
        """
        if not keyword:
            return []
            
        # Search across the pre-normalized, lowercase address string in the Location model
        return Unit.objects.filter(
            status='available',
            property__is_active=True,
            property__location__normalized_address__icontains=keyword.lower()
        ).select_related('property', 'property__location')[:50] # Limit for performance