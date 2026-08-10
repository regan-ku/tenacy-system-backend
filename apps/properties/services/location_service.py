import json
import urllib.request
import urllib.parse
import re
import time
from django.core.exceptions import ValidationError
from ..models import Location
from ..utils.geo_utils import generate_simple_geohash, normalize_address_for_search

class LocationService:
    """
    Manages location data creation, validation, and auto-geocoding.
    """

    @staticmethod
    def validate_location_data(location_data: dict):
        """
        Ensures critical address fields are present before attempting to geocode.
        This enforces the rule: 'wait for the address to be given'.
        """
        city = (location_data.get('city') or '').strip()
        county = (location_data.get('county') or '').strip()
        region = (location_data.get('region') or '').strip()
        
        if not city and not county and not region:
            raise ValidationError(
                "Please provide at least a City, County, or Region to generate map coordinates."
            )

    @staticmethod
    def clean_address_text(text: str) -> str:
        """Removes relational prepositions that confuse geocoders."""
        if not text:
            return ""
        cleaned = re.sub(
            r'\b(next to|opposite|near|behind|adjacent to|close to|by|along)\b',
            '', text, flags=re.IGNORECASE
        )
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
        landmark = LocationService.clean_address_text(location_data.get('landmark', ''))
        estate = LocationService.clean_address_text(location_data.get('estate', ''))
        street = LocationService.clean_address_text(location_data.get('street', ''))
        city = (location_data.get('city') or '').strip()
        county = (location_data.get('county') or '').strip()
        region = (location_data.get('region') or '').strip()

        # ✅ 2. Build a comprehensive query using ALL provided address parts
        all_parts = [landmark, street, estate, city, county, region, "Kenya"]
        full_query = ", ".join([str(p).strip() for p in all_parts if p and str(p).strip()])
        
        # Fallback queries if the highly specific full query fails
        queries_to_try = [full_query]
        
        # Fallback 1: Drop street/landmark and keep Estate + City + County
        fallback_1_parts = [estate, city, county, "Kenya"]
        fallback_1 = ", ".join([str(p).strip() for p in fallback_1_parts if p and str(p).strip()])
        if fallback_1 != full_query and fallback_1 != "Kenya":
            queries_to_try.append(fallback_1)
            
        # Fallback 2: Just City + County
        if city and county:
            fallback_2 = f"{city}, {county}, Kenya"
            if fallback_2 not in queries_to_try:
                queries_to_try.append(fallback_2)
        elif city:
            fallback_2 = f"{city}, Kenya"
            if fallback_2 not in queries_to_try:
                queries_to_try.append(fallback_2)
        elif county:
            fallback_2 = f"{county}, Kenya"
            if fallback_2 not in queries_to_try:
                queries_to_try.append(fallback_2)

        # ✅ 3. Execute queries with proper delay to respect Nominatim's usage policy
        for query in queries_to_try:
            if not query or query == "Kenya":
                continue
                
            try:
                encoded_query = urllib.parse.quote(query)
                url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=1&countrycodes=ke"
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'TennacyPlatform/1.0 (admin@tennacy.com)'}
                )
                
                print(f"🌍 [LocationService] Attempting to geocode: '{query}'...")
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                if data and len(data) > 0:
                    location_data['latitude'] = float(data[0]['lat'])
                    location_data['longitude'] = float(data[0]['lon'])
                    print(f"✅ [LocationService] SUCCESS: Geocoded '{query}' to {location_data['latitude']}, {location_data['longitude']}")
                    return location_data
                else:
                    # ✅ IMPROVED: Log WHY it failed - empty result vs blocked
                    print(f"⚠️ [LocationService] No results for '{query}'. Response: {data}")
                    time.sleep(1.5)  # Increased delay to avoid rate limiting
            except Exception as e:
                print(f"❌ [LocationService] Error geocoding '{query}': {e}")
                time.sleep(1.5)

        print(f"❌ [LocationService] All geocoding attempts failed. Ensure the city/county is valid.")
        return location_data

    @staticmethod
    def create_or_update_location(location_data: dict, instance: Location = None) -> Location:
        print(f"🌍 [LocationService] Received data: {location_data}")
        print(f"🌍 [LocationService] Instance: {instance}")
        
        # ✅ Enforce validation before geocoding
        LocationService.validate_location_data(location_data)
        
        location_data = LocationService.geocode_address(location_data)
        
        # ✅ CRITICAL FIX: Verify coordinates were actually generated
        # This prevents properties from being saved silently without GPS coordinates
        if not location_data.get('latitude') or not location_data.get('longitude'):
            raise ValidationError(
                "Could not generate GPS coordinates from the provided address. "
                "Please verify the city, county, and landmark are correct and try again. "
                "If the problem persists, you may manually enter latitude and longitude."
            )
        
        normalized_address = normalize_address_for_search(
            estate=location_data.get('estate'),
            street=location_data.get('street'),
            city=location_data.get('city'),
            county=location_data.get('county'),
            region=location_data.get('region'),
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
                if key in ['region', 'postal_code', 'estate', 'street', 'landmark', 'latitude', 'longitude', 'city', 'county']:
                    if value is None or str(value).strip() == "":
                        continue 
                setattr(instance, key, value)
                print(f"🌍 [LocationService] Set {key} = {value}")
            
            instance.save()
            print(f"✅ [LocationService] Saved location! City: '{instance.city}', Region: '{instance.region}', Lat: {instance.latitude}, Lon: {instance.longitude}")
            return instance
        else:
            clean_data = {k: v for k, v in location_data.items() if v is not None}
            loc = Location.objects.create(**clean_data)
            print(f"✅ [LocationService] Created new location ID: {loc.id}, Lat: {loc.latitude}, Lon: {loc.longitude}")
            return loc