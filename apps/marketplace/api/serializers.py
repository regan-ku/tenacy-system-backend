from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from apps.properties.models import UnitGroup

from ..models import Listing, UnitGroupAvailability, SavedListing
from ..services import SavedListingService
from ..services.availability_service import AvailabilityService


class UnitGroupAvailabilitySerializer(serializers.ModelSerializer):
    """
    Serializes real-time availability for a unit group (e.g., "3 units remaining").
    """
    availability_text = serializers.CharField(source='get_availability_text', read_only=True)

    class Meta:
        model = UnitGroupAvailability
        fields = [
            'total_units', 
            'available_units', 
            'occupied_units', 
            'is_marketplace_visible', 
            'availability_text'
        ]


class PublicUnitGroupSerializer(serializers.ModelSerializer):
    """
    ✅ UPDATED: Lightweight, PUBLIC serializer for Unit Groups.
    Fetches the group's cover photo from its linked media AND real-time availability.
    """
    cover_photo = serializers.SerializerMethodField()
    # ✅ CRITICAL FIX: Added real-time available units count
    available_units = serializers.SerializerMethodField() 

    class Meta:
        model = UnitGroup
        fields = [
            'id', 'name', 'description', 'unit_type', 'floor_range', 
            'base_rent_amount', 'deposit_amount', 'service_charge', 
            'billing_cycle', 'capacity', 'available_units', 'cover_photo', 'is_active'
        ]

    def get_cover_photo(self, obj):
        # Get the first image linked specifically to this unit group
        first_media = obj.media.filter(media_type='image').first()
        if first_media and first_media.file:
            return first_media.file.url
        return None

    # ✅ NEW: Fetch real-time available units from the tracking model
    def get_available_units(self, obj):
        """
        Fetches the real-time available units count from the UnitGroupAvailability 
        tracking model. Falls back to total capacity if no record exists yet.
        """
        availability = UnitGroupAvailability.objects.filter(unit_group=obj).first()
        
        if availability:
            return availability.available_units
        
        # Fallback: If the sync service hasn't created a record yet, assume all are available
        return obj.capacity


class ListingSerializer(serializers.ModelSerializer):
    """
    Highly optimized serializer for the marketplace landing page grid.
    """
    property_title = serializers.CharField(source='property.title', read_only=True)
    location_summary = serializers.CharField(read_only=True)
    cover_photo = serializers.ImageField(read_only=True)
    
    class Meta:
        model = Listing
        fields = [
            'id', 'property', 'property_title', 'cover_photo', 'location_summary', 
            'min_rent_amount', 'price_period', 'listing_type', 'status'
        ]
        read_only_fields = fields


class ListingDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for the single property/unit detail page.
    ✅ UPDATED: Now bundles Unit Groups and Media directly to bypass private API permissions.
    """
    property_details = serializers.SerializerMethodField()
    unit_group_availability = serializers.SerializerMethodField()
    
    # ✅ NEW FIELDS FOR THE PUBLIC BRIDGE
    available_unit_groups = serializers.SerializerMethodField()
    property_media = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'property', 'title', 'listing_type', 'price_period', 'min_rent_amount', 
            'location_summary', 'cover_photo', 'status', 
            'property_details', 'unit_group_availability',
            'available_unit_groups', 'property_media' # ✅ ADDED HERE
        ]
        read_only_fields = fields

    @extend_schema_field(
        field={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "object"},
                "amenities": {"type": "object"}
            }
        }
    )
    def get_property_details(self, obj):
        property_obj = getattr(obj, 'property', None)
        if not property_obj:
            return {}
            
        location = getattr(property_obj, 'location', None)
        
        return {
            "title": getattr(property_obj, 'title', ''),
            "description": getattr(property_obj, 'description', ''),
            "property_category": getattr(property_obj, 'property_category', ''),
            "property_sub_type": getattr(property_obj, 'property_sub_type', ''),
            "number_of_floors": getattr(property_obj, 'number_of_floors', 1),
            "location": {
                "estate": getattr(location, 'estate', None) if location else None,
                "street": getattr(location, 'street', None) if location else None,
                "city": getattr(location, 'city', None) if location else None,
                "county": getattr(location, 'county', None) if location else None,
                "landmark": getattr(location, 'landmark', None) if location else None,
                "latitude": str(location.latitude) if location and location.latitude else None,
                "longitude": str(location.longitude) if location and location.longitude else None,
            },
            "amenities": {
                "has_water": getattr(property_obj, 'has_water', False),
                "has_electricity": getattr(property_obj, 'has_electricity', False),
                "has_internet": getattr(property_obj, 'has_internet', False),
                "has_cctv": getattr(property_obj, 'has_cctv', False),
                "has_elevator": getattr(property_obj, 'has_elevator', False),
                "has_generator": getattr(property_obj, 'has_generator', False),
                "has_gym": getattr(property_obj, 'has_gym', False),
                "has_swimming_pool": getattr(property_obj, 'has_swimming_pool', False),
                "allows_pets": getattr(property_obj, 'allows_pets', False),
                "parking_spaces": getattr(property_obj, 'parking_spaces', 0),
            }
        }

    @extend_schema_field(UnitGroupAvailabilitySerializer)
    def get_unit_group_availability(self, obj):
        unit_group = getattr(obj, 'unit_group', None)
        if unit_group:
            try:
                summary = AvailabilityService.get_availability_summary(unit_group)
                return summary
            except Exception:
                return None
        return None

    # ✅ NEW: Fetches active Unit Groups for the public
    def get_available_unit_groups(self, obj):
        property_obj = getattr(obj, 'property', None)
        if not property_obj: 
            return []
        
        groups = property_obj.unit_groups.filter(is_active=True, capacity__gt=0)
        # ✅ This now uses the updated PublicUnitGroupSerializer which includes available_units
        return PublicUnitGroupSerializer(groups, many=True).data

    # ✅ UPDATED: Fetches ALL property media EXCEPT sensitive documents
    def get_property_media(self, obj):
        property_obj = getattr(obj, 'property', None)
        if not property_obj: 
            return []
        
        # 🚨 CRITICAL SECURITY FIX: Exclude ownership documents from public view!
        # Only images, videos, virtual tours, and floor plans are exposed.
        media_qs = property_obj.media.exclude(media_type='document').order_by('display_order')
        
        return [
            {
                "id": m.id,
                "file": m.file.url if m.file else (m.url or ""),
                "media_type": m.media_type,
                "caption": m.caption,
                "display_order": m.display_order,
                "unit_group": m.unit_group_id 
            } 
            for m in media_qs if (m.file or m.url)
        ]


class PropertyPublicationActionSerializer(serializers.Serializer):
    """
    Serializer for publish/hide/unpublish/restore actions.
    """
    reason = serializers.CharField(
        required=False, 
        allow_blank=True, 
        help_text="Optional reason for hiding/unpublishing."
    )


class SavedListingSerializer(serializers.ModelSerializer):
    """
    Serializer for user bookmarks/watchlists.
    """
    listing_details = ListingSerializer(source='listing', read_only=True)

    class Meta:
        model = SavedListing
        fields = ['id', 'listing', 'listing_details', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        listing = validated_data['listing']
        notes = validated_data.get('notes', '')
        return SavedListingService.save_listing(user=user, listing=listing, notes=notes)