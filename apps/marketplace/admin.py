from django.contrib import admin
from .models import (
    Listing, PropertyPublication, UnitGroupAvailability, 
    FeaturedListing, SavedListing, ListingView, 
    SearchHistory, MarketplaceVisibilityLog
)

@admin.register(PropertyPublication)
class PropertyPublicationAdmin(admin.ModelAdmin):
    list_display = ('property', 'is_published', 'visibility_status', 'published_at')
    list_filter = ('is_published', 'visibility_status')
    search_fields = ('property__title',)
    readonly_fields = ('published_at', 'unpublished_at', 'created_at', 'updated_at')

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'property', 'listing_type', 'min_rent_amount', 'status', 'created_at')
    list_filter = ('status', 'listing_type')
    search_fields = ('title', 'property__title', 'location_summary')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('property', 'unit_group')

@admin.register(UnitGroupAvailability)
class UnitGroupAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('unit_group', 'total_units', 'available_units', 'is_marketplace_visible', 'last_updated')
    list_filter = ('is_marketplace_visible',)
    search_fields = ('unit_group__name', 'unit_group__property__title')
    readonly_fields = ('last_updated',)

@admin.register(FeaturedListing)
class FeaturedListingAdmin(admin.ModelAdmin):
    list_display = ('listing', 'placement', 'priority', 'is_active', 'start_date', 'end_date')
    list_filter = ('placement', 'is_active')
    search_fields = ('listing__title',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(SavedListing)
class SavedListingAdmin(admin.ModelAdmin):
    list_display = ('user', 'listing', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'listing__title')

@admin.register(ListingView)
class ListingViewAdmin(admin.ModelAdmin):
    list_display = ('listing', 'user', 'source', 'viewed_at', 'ip_address')
    list_filter = ('source', 'viewed_at')
    search_fields = ('listing__title', 'user__email', 'ip_address')
    readonly_fields = ('viewed_at',)

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'search_query', 'results_count', 'searched_at')
    list_filter = ('searched_at',)
    search_fields = ('search_query', 'user__email')
    readonly_fields = ('filters_applied', 'searched_at')

@admin.register(MarketplaceVisibilityLog)
class MarketplaceVisibilityLogAdmin(admin.ModelAdmin):
    list_display = ('property', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('property__title', 'performed_by__email')
    readonly_fields = ('property', 'publication', 'action', 'performed_by', 'reason', 'timestamp')