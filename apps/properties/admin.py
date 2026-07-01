from django.contrib import admin
from .models import Property, Location, UnitGroup, Unit, PropertyMedia, PropertyStaffAssignment # ✅ ADDED PropertyStaffAssignment

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('city', 'county', 'estate', 'landmark', 'latitude', 'longitude')
    search_fields = ('city', 'county', 'estate', 'street', 'landmark', 'normalized_address')
    list_filter = ('city', 'county')


# ✅ NEW: Inlines to show Unit Groups and Units directly on the Property page
class UnitGroupInline(admin.TabularInline):
    model = UnitGroup
    extra = 0
    fields = ('name', 'unit_type', 'floor_range', 'billing_cycle', 'base_rent_amount', 'capacity', 'is_active')
    show_change_link = True
    # Make fields read-only so they can only be edited from the dedicated Unit Group page
    readonly_fields = ('name', 'unit_type', 'floor_range', 'billing_cycle', 'base_rent_amount', 'capacity') 

class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0
    fields = ('unit_code', 'unit_group', 'unit_type', 'floor_number', 'rent_amount', 'status')
    show_change_link = True
    readonly_fields = ('unit_code', 'unit_group', 'unit_type', 'floor_number', 'rent_amount')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'property_sub_type', 'location_city', 'total_units_capacity', 'is_active', 'is_published', 'listing_type', 'created_at')
    list_filter = ('property_category', 'property_sub_type', 'is_active', 'is_published', 'listing_type', 'ownership_status')
    search_fields = ('title', 'description', 'location__city', 'location__county')
    
    readonly_fields = ('created_at', 'updated_at', 'display_location_details')
    raw_id_fields = ('created_by', 'current_manager')
    
    inlines = [UnitGroupInline, UnitInline]
    
    fieldsets = (
        ('Basic Info', {'fields': ('title', 'description', 'cover_photo')}),
        ('Ownership & Management', {'fields': ('created_by', 'current_manager', 'ownership_status')}),
        ('Classification', {'fields': ('property_category', 'property_sub_type', 'construction_type')}),
        
        ('Location Details', {
            'fields': ('location', 'display_location_details'),
            'description': 'The location object is linked here. Full address and GPS details are auto-generated via geo-coding.'
        }),
        
        ('Structure', {'fields': ('number_of_floors', 'total_units_capacity', 'is_single_unit_property')}),
        ('Amenities', {'fields': ('has_water', 'has_electricity', 'has_internet', 'has_cctv', 'has_elevator', 'has_generator', 'has_gym', 'has_swimming_pool', 'allows_pets', 'parking_spaces')}),
        
        ('Marketplace Visibility', {
            'fields': ('is_published', 'listing_type'),
            'description': 'Control whether this property is visible on the public marketplace.'
        }),
        
        ('Status', {'fields': ('is_active', 'created_at', 'updated_at')}),
    )

    def location_city(self, obj):
        if obj.location:
            return f"{obj.location.estate or ''}, {obj.location.city}"
        return "No Location"
    location_city.short_description = 'Location'

    def display_location_details(self, obj):
        if obj.location:
            loc = obj.location
            address_parts = [loc.estate, loc.street, loc.city, loc.county, loc.region]
            full_address = ", ".join([p for p in address_parts if p])
            landmark = f" | Landmark: {loc.landmark}" if loc.landmark else ""
            gps = f" | GPS: {loc.latitude}, {loc.longitude}" if loc.latitude and loc.longitude else ""
            return f"{full_address}{landmark}{gps}"
        return "No location assigned."
    display_location_details.short_description = 'Full Address & Coordinates'


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
    list_display = ('unit_code', 'property_title', 'unit_group_name', 'unit_type', 'floor_number', 'rent_amount', 'status')
    list_filter = ('property_ref', 'unit_group', 'status', 'unit_type', 'billing_cycle')
    search_fields = ('unit_code', 'property_ref__title')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('property_ref', 'unit_group')
    list_select_related = ('property_ref', 'unit_group')

    def property_title(self, obj):
        return obj.property_ref.title
    property_title.short_description = 'Property'
    property_title.admin_order_field = 'property_ref__title'

    def unit_group_name(self, obj):
        return obj.unit_group.name if obj.unit_group else "—"
    unit_group_name.short_description = 'Unit Group'
    unit_group_name.admin_order_field = 'unit_group__name'


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


# ==========================================
# ✅ NEW: PROPERTY STAFF ASSIGNMENT ADMIN
# ==========================================
@admin.register(PropertyStaffAssignment)
class PropertyStaffAssignmentAdmin(admin.ModelAdmin):
    """
    Admin interface for managing operational staff assignments to specific properties.
    Tracks whether the staff member was assigned by the Landlord or the delegated Agency.
    """
    list_display = ('property_title', 'user_email', 'operational_role', 'assigned_by_entity_type', 'assigned_by_agency_name', 'is_active', 'assigned_at')
    list_filter = ('operational_role', 'assigned_by_entity_type', 'is_active')
    search_fields = ('property__title', 'user__email', 'user__profile__full_name')
    readonly_fields = ('assigned_at', 'terminated_at')
    raw_id_fields = ('property', 'user', 'assigned_by_agency')

    def property_title(self, obj):
        return obj.property.title
    property_title.short_description = 'Property'
    property_title.admin_order_field = 'property__title'

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'

    def assigned_by_agency_name(self, obj):
        return obj.assigned_by_agency.name if obj.assigned_by_agency else 'N/A (Direct Landlord)'
    assigned_by_agency_name.short_description = 'Assigned By Agency'