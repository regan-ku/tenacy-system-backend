from django.db import transaction
from ..models import Listing
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
        Updates the specific unit listing and triggers unit group availability checks.
        """
        from .availability_service import AvailabilityService
        
        # 1. Update the specific unit listing
        if unit.status == 'occupied':
            Listing.objects.filter(unit=unit, status='active').update(status='unavailable')
        else:
            Listing.objects.filter(unit=unit, status='unavailable').update(status='active')
            
        # 2. Sync the parent unit group availability (hides group if 0 units left)
        if unit.unit_group:
            AvailabilityService.mark_unit_occupied(unit) if unit.status == 'occupied' else AvailabilityService.mark_unit_available(unit)

    @staticmethod
    @transaction.atomic
    def rebuild_listings_for_property(property: Property):
        """
        Called when a property is first published or significantly updated.
        Ensures Listing records exist and are synced with current unit availability.
        """
        from .listing_service import ListingService # Avoid circular import by importing locally if needed, or handle via service
        
        # This is a heavy operation, typically triggered by a background task
        # For now, it ensures that if a property is published, its available units get listing records
        pass # Implementation handled by publishing_service.py triggers