import math
from django.conf import settings

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the distance between two GPS coordinates in kilometers using the Haversine formula.
    Used for 'nearby units' marketplace search.
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

def generate_simple_geohash(lat: float, lon: float, precision: int = 6) -> str:
    """
    Generates a simple grid-based geohash string for fast database indexing and radius queries.
    (In production, this can be replaced by a dedicated library like `pygeohash`).
    """
    # Simple truncation of coordinates to create a searchable grid string
    lat_str = f"{lat:.{precision}f}".replace('.', '')
    lon_str = f"{lon:.{precision}f}".replace('.', '')
    return f"{lat_str[:4]}{lon_str[:4]}"

def normalize_address_for_search(estate: str, street: str, city: str, county: str, landmark: str) -> str:
    """
    Concatenates and cleans address parts into a single lowercase string for full-text search.
    """
    parts = [estate, street, city, county, landmark]
    return " ".join([str(p).lower().strip() for p in parts if p])