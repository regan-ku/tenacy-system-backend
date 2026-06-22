from django.contrib import admin
from .models import Property, Location, UnitGroup, Unit, PropertyMedia

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('city', 'county', 'estate', 'landmark', 'latitude', 'longitude')
    search_fields = ('city', 'county', 'estate', 'street', 'landmark', 'normalized_address')
    list_filter = ('city', 'county')

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    # ✅ ADDED: is_published and listing_type to the list view
    list_display = ('title', 'property_sub_type', 'location_city', 'total_units_capacity', 'is_active', 'is_published', 'listing_type', 'created_at')
    
    # ✅ ADDED: Filters for marketplace visibility
    list_filter = ('property_category', 'property_sub_type', 'is_active', 'is_published', 'listing_type', 'ownership_status')
    search_fields = ('title', 'description', 'location__city', 'location__county')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('created_by', 'current_manager')
    
    fieldsets = (
        ('Basic Info', {'fields': ('title', 'description', 'cover_photo')}),
        ('Ownership & Management', {'fields': ('created_by', 'current_manager', 'ownership_status')}),
        ('Classification', {'fields': ('property_category', 'property_sub_type', 'construction_type')}),
        ('Structure', {'fields': ('number_of_floors', 'total_units_capacity', 'is_single_unit_property')}),
        ('Amenities', {'fields': ('has_water', 'has_electricity', 'has_internet', 'has_cctv', 'has_elevator', 'has_generator', 'has_gym', 'has_swimming_pool', 'allows_pets', 'parking_spaces')}),
        
        # ✅ NEW: Dedicated Marketplace Visibility Section
        ('Marketplace Visibility', {
            'fields': ('is_published', 'listing_type'),
            'description': 'Control whether this property is visible on the public marketplace.'
        }),
        
        ('Status', {'fields': ('is_active', 'created_at', 'updated_at')}),
    )

    def location_city(self, obj):
        return f"{obj.location.estate or ''}, {obj.location.city}"
    location_city.short_description = 'Location'

@admin.register(UnitGroup)
class UnitGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'property_title', 'unit_type', 'billing_cycle', 'base_rent_amount', 'capacity', 'is_active')
    list_filter = ('unit_type', 'billing_cycle', 'is_active')
    search_fields = ('name', 'property__title')
    raw_id_fields = ('property',)

    def property_title(self, obj):
        return obj.property.title
    property_title.short_description = 'Property'

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('unit_code', 'property_title', 'unit_type', 'floor_number', 'rent_amount', 'status', 'created_at')
    list_filter = ('status', 'unit_type', 'billing_cycle')
    search_fields = ('unit_code', 'property_ref__title')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('property_ref', 'unit_group')

    def property_title(self, obj):
        return obj.property_ref.title
    property_title.short_description = 'Property'

@admin.register(PropertyMedia)
class PropertyMediaAdmin(admin.ModelAdmin):
    list_display = ('property_title', 'unit_code', 'media_type', 'caption', 'display_order', 'created_at')
    list_filter = ('media_type',)
    search_fields = ('property_ref__title', 'caption')
    raw_id_fields = ('property_ref', 'unit')

    def property_title(self, obj):
        return obj.property_ref.title
    property_title.short_description = 'Property'

    def unit_code(self, obj):
        return obj.unit.unit_code if obj.unit else 'N/A'
    unit_code.short_description = 'Unit Code'