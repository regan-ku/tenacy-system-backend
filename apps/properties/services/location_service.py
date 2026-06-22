from django.core.exceptions import ValidationError
from ..models import Location
from ..utils.geo_utils import generate_simple_geohash, normalize_address_for_search

class LocationService:
    """
    Manages location data creation, validation, and geo-intelligence generation.
    """

    @staticmethod
    def validate_location_data(location_data: dict):
        """Ensures mandatory location fields are present."""
        required_fields = ['city', 'county', 'landmark']
        for field in required_fields:
            if not location_data.get(field):
                raise ValidationError(f"Location '{field}' is required.")

    @staticmethod
    def create_or_update_location(location_data: dict, instance: Location = None) -> Location:
        """
        Creates or updates a location, auto-generating normalized addresses and geohashes.
        """
        LocationService.validate_location_data(location_data)
        
        # Auto-generate normalized address for search
        normalized_address = normalize_address_for_search(
            estate=location_data.get('estate'),
            street=location_data.get('street'),
            city=location_data.get('city'),
            county=location_data.get('county'),
            landmark=location_data.get('landmark')
        )
        location_data['normalized_address'] = normalized_address

        # Auto-generate simple geohash if lat/lon are provided
        if location_data.get('latitude') and location_data.get('longitude'):
            location_data['geohash'] = generate_simple_geohash(
                float(location_data['latitude']), 
                float(location_data['longitude'])
            )

        if instance:
            for key, value in location_data.items():
                setattr(instance, key, value)
            instance.save()
            return instance
        else:
            return Location.objects.create(**location_data)