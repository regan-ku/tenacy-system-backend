from django.db import transaction
from django.db.models import Min
from ..models import Listing, UnitGroupAvailability
from apps.properties.models import UnitGroup, Property, Unit


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
        ✅ FIXED: Price now comes from the CHEAPEST AVAILABLE UNIT (live from DB),
        falling back to the group's base_rent_amount only when no units exist yet.
        """
        property_obj = unit_group.property

        # Check if property is published and visible
        if not hasattr(property_obj, 'publication') or not property_obj.publication.is_published:
            return None

        if property_obj.publication.visibility_status != 'visible':
            return None

        # ✅ LIVE availability calculated from real units (not stale numbers)
        total_units = Unit.objects.filter(unit_group=unit_group).count() or unit_group.capacity
        available_units = Unit.objects.filter(unit_group=unit_group, status='available').count()

        availability, _ = UnitGroupAvailability.objects.get_or_create(
            unit_group=unit_group,
            defaults={'total_units': total_units, 'available_units': available_units},
        )

        # Keep the availability record in sync with real unit statuses
        if availability.total_units != total_units or availability.available_units != available_units:
            availability.total_units = total_units
            availability.available_units = available_units
            availability.save(update_fields=['total_units', 'available_units'])

        # Determine listing status based on availability
        listing_status = 'active' if availability.is_marketplace_visible else 'unavailable'

        # ✅ THE FIX: "Starting from" price = cheapest AVAILABLE unit in this group.
        # Falls back to the group base rent only if no units are available.
        cheapest_unit_rent = Unit.objects.filter(
            unit_group=unit_group, status='available'
        ).aggregate(min_rent=Min('rent_amount'))['min_rent']

        effective_price = (
            cheapest_unit_rent
            if cheapest_unit_rent is not None
            else unit_group.base_rent_amount
        )

        # Create or update the listing
        listing, created = Listing.objects.update_or_create(
            property=property_obj,
            unit_group=unit_group,
            listing_type='rental',
            defaults={
                'title': f"{unit_group.get_unit_type_display()} in {property_obj.location.city}",
                'description': property_obj.description,
                'price': effective_price,
                'price_period': f"per {unit_group.billing_cycle}",
                'status': listing_status,
                'cover_photo': property_obj.cover_photo,
                'location_summary': f"{property_obj.location.estate or ''}, {property_obj.location.city}".strip(', '),
                'min_rent_amount': effective_price,
                # ✅ Remove this line if you haven't added the available_units field to Listing yet
                'available_units': available_units,
            },
        )
        return listing

    @staticmethod
    @transaction.atomic
    def update_listing_availability(unit_group: UnitGroup):
        """
        Called when unit occupancy changes.
        ✅ Now delegates to the full sync so price + availability stay in lockstep.
        """
        return UnitGroupListingService.sync_unit_group_to_marketplace(unit_group)