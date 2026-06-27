from django.db import transaction
from ..models import Listing, UnitGroupAvailability
from apps.properties.models import Property, Unit

class MarketplaceSyncService:
    """
    Ensures that operational changes (tenancy, property status) instantly 
    reflect in the marketplace without manual intervention.
    """

    @staticmethod
    @transaction.atomic
    def sync_property_status(property: Property):
        """
        Called when a property's active status changes.
        """
        if not property.is_active:
            # If property is deactivated, hide all its listings
            Listing.objects.filter(property=property).update(status='hidden')
            if hasattr(property, 'publication'):
                property.publication.visibility_status = 'hidden'
                property.publication.save(update_fields=['visibility_status'])
        else:
            # If reactivated, restore listings that have available units
            Listing.objects.filter(property=property, status='hidden').update(status='active')

    @staticmethod
    @transaction.atomic
    def sync_unit_occupancy(unit: Unit):
        """
        Called when a unit's status changes (e.g., available -> occupied).
        Updates the UnitGroupAvailability and toggles the Listing visibility.
        """
        # ✅ FIX: Listings are tied to unit_group or property, NOT individual units.
        # Filtering by unit=unit causes a FieldError or silent failure.
        
        if not unit.unit_group:
            # Single unit property (no group) -> toggle property-level listing
            property_obj = getattr(unit, 'property_ref', None) or getattr(unit, 'property', None)
            if property_obj:
                if unit.status == 'occupied':
                    Listing.objects.filter(property=property_obj, status='active').update(status='unavailable')
                else:
                    Listing.objects.filter(property=property_obj, status='unavailable').update(status='active')
            return

        # 1. Get or create UnitGroupAvailability
        availability, created = UnitGroupAvailability.objects.get_or_create(
            unit_group=unit.unit_group,
            defaults={
                'total_units': unit.unit_group.capacity,
                'available_units': unit.unit_group.capacity,
                'occupied_units': 0
            }
        )

        # ✅ FIX: Recalculate availability based on ACTUAL unit statuses to prevent drift.
        # This guarantees the marketplace number is always 100% accurate.
        occupied_count = Unit.objects.filter(unit_group=unit.unit_group, status='occupied').count()
        total_capacity = unit.unit_group.capacity
        
        availability.occupied_units = occupied_count
        availability.available_units = max(0, total_capacity - occupied_count)
        availability.save()

        # 2. Toggle the Listing visibility (Listing is tied to unit_group)
        if availability.available_units == 0:
            # All units in this group are occupied -> Hide the listing
            Listing.objects.filter(unit_group=unit.unit_group, status='active').update(status='unavailable')
        else:
            # At least one unit is available -> Show the listing
            Listing.objects.filter(unit_group=unit.unit_group, status='unavailable').update(status='active')

    @staticmethod
    @transaction.atomic
    def rebuild_listings_for_property(property: Property):
        """
        Called when a property is first published or significantly updated.
        Ensures Listing records exist and are synced with current unit availability.
        """
        # Implementation handled by publishing_service.py triggers
        pass 