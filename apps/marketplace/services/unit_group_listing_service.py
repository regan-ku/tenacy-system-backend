from django.db import transaction
from ..models import Listing, UnitGroupAvailability
from apps.properties.models import UnitGroup, Property

class UnitGroupListingService:
    """
    Bridges the Properties app (Unit Groups) with the Marketplace app (Listings).
    Ensures that pricing, availability, and unit group changes automatically reflect in the marketplace.
    """

    @staticmethod
    @transaction.atomic
    def sync_unit_group_to_marketplace(unit_group: UnitGroup):
        """
        Creates or updates a marketplace listing for a specific unit group.
        Ensures the listing reflects current pricing and availability.
        """
        property_obj = unit_group.property
        
        # Check if property is published and visible
        if not hasattr(property_obj, 'publication') or not property_obj.publication.is_published:
            return None
            
        if property_obj.publication.visibility_status != 'visible':
            return None

        # Get availability summary
        availability, _ = UnitGroupAvailability.objects.get_or_create(
            unit_group=unit_group,
            defaults={'total_units': unit_group.capacity, 'available_units': unit_group.capacity}
        )

        # Determine listing status based on availability
        listing_status = 'active' if availability.is_marketplace_visible else 'unavailable'

        # Create or update the listing
        listing, created = Listing.objects.update_or_create(
            property=property_obj,
            unit_group=unit_group,
            listing_type='rental',
            defaults={
                'title': f"{unit_group.get_unit_type_display()} in {property_obj.location.city}",
                'description': property_obj.description,
                'price': unit_group.base_rent_amount,
                'price_period': f"per {unit_group.billing_cycle}",
                'status': listing_status,
                'cover_photo': property_obj.cover_photo,
                'location_summary': f"{property_obj.location.estate or ''}, {property_obj.location.city}".strip(', '),
                'min_rent_amount': unit_group.base_rent_amount
            }
        )
        return listing

    @staticmethod
    @transaction.atomic
    def update_listing_availability(unit_group: UnitGroup):
        """
        Called when unit occupancy changes. Updates the listing status to 'unavailable' if fully occupied.
        """
        availability = UnitGroupAvailability.objects.filter(unit_group=unit_group).first()
        if availability:
            Listing.objects.filter(unit_group=unit_group).update(
                status='active' if availability.is_marketplace_visible else 'unavailable'
            )