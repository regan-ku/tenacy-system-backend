import math
from django.db.models import Q
from ..models import Listing

class GeoMarketplaceService:
    """
    Handles geo-based search and nearby listing discovery for the public marketplace.
    Uses bounding box filtering followed by precise Haversine distance calculation.
    """

    @staticmethod
    def find_nearby_available_units(latitude: float, longitude: float, radius_km: float = 5.0) -> list:
        """
        Finds available listings within a specific radius of a given coordinate.
        Optimized for performance using a two-step filtering approach.
        """
        # 1. Rough bounding box calculation (1 degree lat/lon is approx 111km)
        degree_offset = radius_km / 111.0
        
        min_lat = latitude - degree_offset
        max_lat = latitude + degree_offset
        min_lon = longitude - degree_offset
        max_lon = longitude + degree_offset

        # 2. Fast database query for LISTINGS that are within the bounding box and publicly visible
        # ✅ FIX: Q objects (positional arguments) MUST come before keyword arguments
        candidate_listings = Listing.objects.filter(
            Q(unit__isnull=True) | Q(unit__status='available'), # <-- POSITIONAL ARGUMENT FIRST
            status='active',
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible',
            property__location__latitude__gte=min_lat,
            property__location__latitude__lte=max_lat,
            property__location__longitude__gte=min_lon,
            property__location__longitude__lte=max_lon
        ).select_related('property', 'property__location', 'unit_group').distinct()

        # 3. Precise distance filtering in Python (Haversine formula)
        nearby_listings = []
        for listing in candidate_listings:
            loc = listing.property.location
            if loc.latitude and loc.longitude:
                distance = GeoMarketplaceService._calculate_distance(
                    float(latitude), float(longitude),
                    float(loc.latitude), float(loc.longitude)
                )
                if distance <= radius_km:
                    listing.distance_km = round(distance, 2) # Attach dynamically for frontend
                    nearby_listings.append(listing)

        # Sort by distance (closest first)
        return sorted(nearby_listings, key=lambda x: x.distance_km)

    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates the distance between two GPS coordinates in kilometers.
        """
        R = 6371.0  # Earth radius in kilometers

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c