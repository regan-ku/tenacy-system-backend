from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ..models import Property, Location, UnitGroup, Unit, PropertyMedia
from ..models.enums import PropertyCategory, PropertySubType, UnitType, UnitStatus, BillingCycle, ConstructionType
from ..services import PropertyService, UnitGroupService, UnitService, LocationService, MediaService


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            'estate', 'street', 'city', 'county', 'region', 'postal_code', 
            'landmark', 
            'latitude', 'longitude'
        ]

    def create(self, validated_data):
        return LocationService.create_or_update_location(validated_data)

    def update(self, instance, validated_data):
        return LocationService.create_or_update_location(validated_data, instance=instance)


class PropertySerializer(serializers.ModelSerializer):
    location = LocationSerializer(write_only=True)
    location_details = serializers.SerializerMethodField()

    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    property_category = serializers.ChoiceField(choices=PropertyCategory.choices)
    property_sub_type = serializers.ChoiceField(choices=PropertySubType.choices)
    construction_type = serializers.ChoiceField(choices=ConstructionType.choices, required=False)

    # ✅ NEW: Expose Landlord Name and Delegation Details for Agency Context
    landlord_name = serializers.SerializerMethodField()
    delegation_info = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description', 'cover_photo', 'created_by_email', 
            'ownership_status', 'property_category', 'property_sub_type', 
            'construction_type', 'number_of_floors', 'total_units_capacity', 
            'is_single_unit_property', 'has_water', 'has_electricity', 'has_internet', 
            'has_cctv', 'has_elevator', 'has_generator', 'has_gym', 'has_swimming_pool', 
            'listing_type', 'is_published', 'allows_pets', 'parking_spaces',
            'location', 'is_active', 'location_details', 
            'landlord_name', 'delegation_info' # ✅ Added to fields list
        ]
        read_only_fields = ['id', 'created_by_email', 'is_active', 'location_details', 'landlord_name', 'delegation_info']
        extra_kwargs = {
            'cover_photo': {'help_text': 'Main display image for the property.'}
        }

    @extend_schema_field(LocationSerializer)
    def get_location_details(self, obj):
        return LocationSerializer(obj.location).data if obj.location else None

    def get_landlord_name(self, obj):
        """Safely fetches the landlord's full name, falling back to email."""
        try:
            # Try to get from related Profile model first (assumes related_name='profile')
            if hasattr(obj.created_by, 'profile') and obj.created_by.profile.full_name:
                return obj.created_by.profile.full_name
            # Fallback to User model method if it exists
            if hasattr(obj.created_by, 'get_full_name'):
                name = obj.created_by.get_full_name()
                if name: 
                    return name
        except Exception:
            pass
        return obj.created_by.email

    def get_delegation_info(self, obj):
        """
        ✅ OPTIMIZED: Reads the prefetched 'active_agency_delegation' attribute 
        set by the ViewSet. This prevents N+1 database queries.
        """
        if hasattr(obj, 'active_agency_delegation') and obj.active_agency_delegation:
            delegation = obj.active_agency_delegation[0]
            return {
                'delegation_type': delegation.delegation_type,
                'custom_permissions': delegation.custom_permissions,
                'status': delegation.status,
            }
        return None

    def create(self, validated_data):
        user = self.context['request'].user
        location_data = validated_data.pop('location', {})
        
        return PropertyService.create_property(
            created_by_user=user,
            location_data=location_data,
            **validated_data
        )

    def update(self, instance, validated_data):
        user = self.context['request'].user
        if 'location' in validated_data:
            location_data = validated_data.pop('location')
            LocationService.create_or_update_location(location_data, instance=instance.location)
            
        return PropertyService.update_property(instance, user, validated_data)


class UnitGroupSerializer(serializers.ModelSerializer):
    unit_type = serializers.ChoiceField(choices=UnitType.choices)
    billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices)

    class Meta:
        model = UnitGroup
        fields = [
            'id', 'name', 'description', 'unit_type', 'floor_range', 
            'billing_cycle', 'billing_date', 'base_rent_amount',  
            'service_charge', 'deposit_amount', 'currency', 'capacity', 
            'allows_pets_override', 'is_active', 
            'cover_photo' 
        ]
        extra_kwargs = {
            'name': {'help_text': "e.g., 'Block A', 'Wing 1'."},
            'floor_range': {'help_text': "e.g., 'Ground', '1-3'."},
            'cover_photo': {'help_text': 'Upload a cover image for this specific unit group.'}
        }

    def create(self, validated_data):
        property_obj = self.context['property']
        user = self.context['request'].user
        
        return UnitGroupService.create_unit_group(
            property=property_obj,
            created_by_user=user,
            **validated_data
        )


class UnitSerializer(serializers.ModelSerializer):
    # ✅ FIX 1: Use 'property_ref' instead of 'property'
    property_title = serializers.CharField(source='property_ref.title', read_only=True)
    unit_group_name = serializers.CharField(source='unit_group.name', read_only=True, allow_null=True)
    
    # ✅ FIX 2: These fields are INHERITED, not stored directly on the Unit model.
    # We use SerializerMethodField to fetch them from the related Property/UnitGroup models.
    allows_pets = serializers.SerializerMethodField()
    parking_spaces = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    
    status = serializers.ChoiceField(choices=UnitStatus.choices, required=False)

    class Meta:
        model = Unit
        fields = [
            'id', 'property_title', 'unit_group_name', 'unit_code', 'unit_type', 
            'floor_number', 'rent_amount', 'deposit_amount', 'service_charge', 
            'currency', 'billing_cycle', 'billing_date', 'status', 
            'allows_pets', 'parking_spaces', 'cover_photo', 'created_at'
        ]
        read_only_fields = [
            'id', 'property_title', 'unit_group_name', 'currency', 
            'allows_pets', 'parking_spaces', 'created_at'
        ]
        extra_kwargs = {
            'cover_photo': {'help_text': 'Main display image for this specific unit.'}
        }

    # ✅ FIX 3: Define how to fetch the inherited fields dynamically
    def get_allows_pets(self, obj):
        return obj.property_ref.allows_pets

    def get_parking_spaces(self, obj):
        return obj.property_ref.parking_spaces

    def get_currency(self, obj):
        return obj.unit_group.currency if obj.unit_group else 'KES'

    def update(self, instance, validated_data):
        return UnitService.update_unit(instance, validated_data)


class PropertyMediaSerializer(serializers.ModelSerializer):
    media_type = serializers.ChoiceField(choices=PropertyMedia.MediaType.choices)
    property_title = serializers.CharField(source='property_ref.title', read_only=True, allow_null=True)

    class Meta:
        model = PropertyMedia
        fields = [
            'id', 'property_ref', 'property_title', 'unit', 'unit_group', 
            'media_type', 'file', 'url', 'caption', 'display_order', 'created_at'
        ]
        # ✅ Make property_ref write_only since we'll set it in the view
        extra_kwargs = {
            'file': {'help_text': 'Upload image, video, floor plan, or document.'},
            'url': {'help_text': 'Optional external link (e.g., YouTube virtual tour).'},
            'property_ref': {'write_only': True}
        }

    def create(self, validated_data):
        return super().create(validated_data)