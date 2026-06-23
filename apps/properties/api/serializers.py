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
            'landmark', 'latitude', 'longitude'
        ]
        extra_kwargs = {
            'region': {'required': False, 'allow_blank': True, 'allow_null': True},
            'postal_code': {'required': False, 'allow_blank': True, 'allow_null': True},
            'estate': {'required': False, 'allow_blank': True, 'allow_null': True},
            'street': {'required': False, 'allow_blank': True, 'allow_null': True},
            'landmark': {'required': False, 'allow_blank': True, 'allow_null': True},
            'city': {'required': False, 'allow_blank': True, 'allow_null': True},
            'county': {'required': False, 'allow_blank': True, 'allow_null': True},
            'latitude': {'required': False, 'allow_null': True},
            'longitude': {'required': False, 'allow_null': True},
        }

    def create(self, validated_data):
        return LocationService.create_or_update_location(validated_data)

    def update(self, instance, validated_data):
        return LocationService.create_or_update_location(validated_data, instance=instance)


class PropertySerializer(serializers.ModelSerializer):
    location = LocationSerializer(write_only=True, required=False) 
    location_details = serializers.SerializerMethodField()

    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    property_category = serializers.ChoiceField(choices=PropertyCategory.choices)
    property_sub_type = serializers.ChoiceField(choices=PropertySubType.choices)
    construction_type = serializers.ChoiceField(choices=ConstructionType.choices, required=False)

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
            'landlord_name', 'delegation_info'
        ]
        read_only_fields = ['id', 'created_by_email', 'is_active', 'location_details', 'landlord_name', 'delegation_info']

    @extend_schema_field(LocationSerializer)
    def get_location_details(self, obj):
        return LocationSerializer(obj.location).data if obj.location else None

    def get_landlord_name(self, obj):
        try:
            if hasattr(obj.created_by, 'profile') and obj.created_by.profile.full_name:
                return obj.created_by.profile.full_name
            if hasattr(obj.created_by, 'get_full_name'):
                name = obj.created_by.get_full_name()
                if name: return name
        except Exception:
            pass
        return obj.created_by.email

    def get_delegation_info(self, obj):
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
        # 🔍 DEBUG: See exactly what keys the frontend sent
        print(f"🔥 [PropertySerializer] UPDATE CALLED! Keys received: {list(validated_data.keys())}")
        
        user = self.context['request'].user
        
        if 'location' in validated_data:
            print(f"📍 [PropertySerializer] Location data found: {validated_data['location']}")
            location_data = validated_data.pop('location')
            if location_data and instance.location: 
                print(f"🛠️ [PropertySerializer] Calling LocationService for instance {instance.location.id}")
                LocationService.create_or_update_location(location_data, instance=instance.location)
            elif location_data and not instance.location:
                print(f"🆕 [PropertySerializer] Creating new location")
                instance.location = LocationService.create_or_update_location(location_data)
                instance.save(update_fields=['location'])
        else:
            print("⚠️ [PropertySerializer] NO LOCATION DATA IN VALIDATED_DATA! The frontend didn't send the 'location' key.")
            
        return PropertyService.update_property(instance, user, validated_data)


# ... (Keep UnitGroupSerializer, UnitSerializer, and PropertyMediaSerializer exactly as they are) ...


class UnitGroupSerializer(serializers.ModelSerializer):
    unit_type = serializers.ChoiceField(choices=UnitType.choices)
    billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices)
    
    # ✅ NEW: Real-time count of actual units generated in this group
    actual_units_count = serializers.SerializerMethodField()

    class Meta:
        model = UnitGroup
        fields = [
            'id', 'name', 'description', 'unit_type', 'floor_range', 
            'billing_cycle', 'billing_date', 'base_rent_amount',  
            'service_charge', 'deposit_amount', 'currency', 'capacity', 
            'allows_pets_override', 'is_active', 'cover_photo',
            'actual_units_count' # ✅ Added to fields list
        ]
        extra_kwargs = {
            'name': {'help_text': "e.g., 'Block A', 'Wing 1'."},
            'floor_range': {'help_text': "e.g., 'Ground', '1-3'."},
            'cover_photo': {'help_text': 'Upload a cover image for this specific unit group.'}
        }

    def get_actual_units_count(self, obj):
        """Returns the exact number of units currently existing in this group."""
        return obj.units.count()

    def create(self, validated_data):
        property_obj = self.context['property']
        user = self.context['request'].user
        
        return UnitGroupService.create_unit_group(
            property=property_obj,
            created_by_user=user,
            **validated_data
        )
    
    def update(self, instance, validated_data):
        return UnitGroupService.update_unit_group(instance, validated_data)


class UnitSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property_ref.title', read_only=True)
    unit_group_name = serializers.CharField(source='unit_group.name', read_only=True, allow_null=True)
    unit_group_id = serializers.IntegerField(source='unit_group.id', read_only=True, allow_null=True)
    
    unit_group = serializers.PrimaryKeyRelatedField(
        queryset=UnitGroup.objects.all(), 
        write_only=True, 
        required=False, 
        allow_null=True
    )
    
    allows_pets = serializers.SerializerMethodField()
    parking_spaces = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    
    status = serializers.ChoiceField(choices=UnitStatus.choices, required=False)

    class Meta:
        model = Unit
        fields = [
            'id', 'property_title', 'unit_group_name', 'unit_group_id', 'unit_group', 
            'unit_code', 'unit_type', 
            'floor_number', 'rent_amount', 'deposit_amount', 'service_charge', 
            'currency', 'billing_cycle', 'billing_date', 'status', 
            'allows_pets', 'parking_spaces', 'cover_photo', 'created_at'
        ]
        read_only_fields = [
            'id', 'property_title', 'unit_group_name', 'unit_group_id', 'currency', 
            'allows_pets', 'parking_spaces', 'created_at', 'unit_code' 
        ]
        extra_kwargs = {
            'cover_photo': {'help_text': 'Main display image for the specific unit.'},
            'unit_type': {'required': False},
            'rent_amount': {'required': False},
            'deposit_amount': {'required': False},
            'service_charge': {'required': False},
            'billing_cycle': {'required': False},
            'billing_date': {'required': False},
        }

    def get_allows_pets(self, obj):
        return obj.property_ref.allows_pets

    def get_parking_spaces(self, obj):
        return obj.property_ref.parking_spaces

    def get_currency(self, obj):
        return obj.unit_group.currency if obj.unit_group else 'KES'

    def create(self, validated_data):
        property_obj = self.context.get('property')
        if not property_obj:
            raise serializers.ValidationError("Property context is missing.")
            
        unit_group = validated_data.pop('unit_group', None)
        floor_number = validated_data.get('floor_number', 0)
        
        if unit_group:
            if unit_group.property != property_obj:
                raise serializers.ValidationError({"unit_group": "This unit group does not belong to the specified property."})
            return UnitService.create_unit_in_group(property_obj, unit_group, floor_number)
        else:
            if not validated_data.get('unit_type'):
                raise serializers.ValidationError({"unit_type": "This field is required when not adding to a unit group."})
            if 'rent_amount' not in validated_data:
                raise serializers.ValidationError({"rent_amount": "This field is required when not adding to a unit group."})
                
            return UnitService.create_single_unit(
                property_obj=property_obj,
                unit_type=validated_data.get('unit_type'),
                floor_number=floor_number,
                rent_amount=validated_data.get('rent_amount', 0),
                deposit_amount=validated_data.get('deposit_amount', 0),
                service_charge=validated_data.get('service_charge', 0),
                billing_cycle=validated_data.get('billing_cycle', 'monthly'),
                billing_date=validated_data.get('billing_date', 1),
            )

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
        extra_kwargs = {
            'file': {'help_text': 'Upload image, video, floor plan, or document.'},
            'url': {'help_text': 'Optional external link.'},
            'property_ref': {'write_only': True}
        }

    def create(self, validated_data):
        return super().create(validated_data)