import json
import urllib.request
import urllib.parse
import re
from django.core.exceptions import ValidationError
from ..models import Location
from ..utils.geo_utils import generate_simple_geohash, normalize_address_for_search

class LocationService:
    """
    Manages location data creation, validation, and auto-geocoding.
    """

    @staticmethod
    def validate_location_data(location_data: dict):
        pass

    @staticmethod
    def clean_address_text(text: str) -> str:
        """Removes relational prepositions that confuse geocoders."""
        if not text:
            return ""
        # Remove words like "Next to", "Opposite", "Near", "Behind"
        cleaned = re.sub(r'\b(next to|opposite|near|behind|adjacent to|close to|by|along)\b', '', text, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def geocode_address(location_data: dict):
        lat = location_data.get('latitude')
        lon = location_data.get('longitude')
        
        # If valid coordinates already exist, skip geocoding
        if lat and lon:
            try:
                location_data['latitude'] = float(lat)
                location_data['longitude'] = float(lon)
                return location_data
            except (ValueError, TypeError):
                pass 

        # ✅ 1. Clean the text fields
        landmark = LocationService.clean_address_text(location_data.get('landmark'))
        estate = LocationService.clean_address_text(location_data.get('estate'))
        city = location_data.get('city')
        county = location_data.get('county')

        # ✅ 2. Build a list of queries to try, from most specific to least specific
        queries_to_try = []
        
        # Query 1: Full address (cleaned)
        full_parts = [landmark, estate, location_data.get('street'), city, county]
        full_query = ", ".join([str(p).strip() for p in full_parts if p and str(p).strip()])
        if full_query:
            queries_to_try.append(full_query)
            
        # Query 2: Estate + City (Fallback if landmark confuses the API)
        if estate and city:
            queries_to_try.append(f"{estate}, {city}")
            
        # Query 3: Just City + County (Last resort)
        if city and county:
            queries_to_try.append(f"{city}, {county}")

        # ✅ 3. Try each query until one succeeds
        for query in queries_to_try:
            try:
                encoded_query = urllib.parse.quote(query)
                # ✅ CRITICAL FIX: Add countrycodes=ke to restrict search to Kenya
                url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=1&countrycodes=ke"
                req = urllib.request.Request(url, headers={'User-Agent': 'TennacyPlatform/1.0 (admin@tennacy.com)'})
                
                print(f"🌍 [LocationService] Attempting to geocode: '{query}'...")
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                if data and len(data) > 0:
                    location_data['latitude'] = float(data[0]['lat'])
                    location_data['longitude'] = float(data[0]['lon'])
                    print(f"✅ [LocationService] SUCCESS: Geocoded '{query}' to {location_data['latitude']}, {location_data['longitude']}")
                    return location_data # Exit early if successful
                else:
                    print(f"⚠️ [LocationService] No results for '{query}'. Trying fallback...")
            except Exception as e:
                print(f"❌ [LocationService] Error geocoding '{query}': {e}")

        print(f"❌ [LocationService] All geocoding attempts failed for this address.")
        return location_data

    @staticmethod
    def create_or_update_location(location_data: dict, instance: Location = None) -> Location:
        print(f"🌍 [LocationService] Received data: {location_data}")
        print(f"🌍 [LocationService] Instance: {instance}")
        
        LocationService.validate_location_data(location_data)
        location_data = LocationService.geocode_address(location_data)
        
        normalized_address = normalize_address_for_search(
            estate=location_data.get('estate'),
            street=location_data.get('street'),
            city=location_data.get('city'),
            county=location_data.get('county'),
            landmark=location_data.get('landmark')
        )
        location_data['normalized_address'] = normalized_address

        if location_data.get('latitude') and location_data.get('longitude'):
            try:
                location_data['geohash'] = generate_simple_geohash(
                    float(location_data['latitude']), 
                    float(location_data['longitude'])
                )
            except Exception:
                pass

        if instance:
            print(f"🛠️ [LocationService] Updating existing location ID: {instance.id}")
            for key, value in location_data.items():
                if key in ['region', 'postal_code', 'estate', 'street', 'landmark', 'latitude', 'longitude']:
                    if value is None or str(value).strip() == "":
                        continue 
                setattr(instance, key, value)
                print(f"🌍 [LocationService] Set {key} = {value}")
            
            instance.save()
            print(f"✅ [LocationService] Saved location! City is now: '{instance.city}', Region: '{instance.region}'")
            return instance
        else:
            clean_data = {k: v for k, v in location_data.items() if v is not None}
            loc = Location.objects.create(**clean_data)
            print(f"✅ [LocationService] Created new location ID: {loc.id}")
            return loc