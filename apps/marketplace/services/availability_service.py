from django.db import transaction
from ..models import UnitGroupAvailability, Listing
from apps.properties.models import Unit

class AvailabilityService:
    """
    Syncs unit occupancy with marketplace availability.
    Automatically hides unit groups when fully occupied and restores them when units become available.
    """

    @staticmethod
    @transaction.atomic
    def mark_unit_occupied(unit: Unit):
        """
        Called when a tenancy becomes active.
        Removes the unit from marketplace availability and updates group counts.
        """
        # 1. Update unit status (if not already done by tenancy app)
        if unit.status != 'occupied':
            unit.status = 'occupied'
            unit.save(update_fields=['status'])

        # 2. Update Unit Group Availability
        if unit.unit_group:
            availability, created = UnitGroupAvailability.objects.get_or_create(
                unit_group=unit.unit_group,
                defaults={
                    'total_units': unit.unit_group.capacity,
                    'available_units': max(0, unit.unit_group.capacity - 1),
                    'occupied_units': 1
                }
            )
            
            if not created:
                availability.available_units = max(0, availability.available_units - 1)
                availability.occupied_units += 1
                availability.save()

        # 3. Update Listing status if it was tied to this specific unit
        Listing.objects.filter(unit=unit, status='active').update(status='unavailable')

    @staticmethod
    @transaction.atomic
    def mark_unit_available(unit: Unit):
        """
        Called when a tenancy is terminated or an application is rejected.
        Makes the unit visible in the marketplace and updates group counts.
        """
        # 1. Update unit status
        if unit.status != 'available':
            unit.status = 'available'
            unit.save(update_fields=['status'])

        # 2. Update Unit Group Availability
        if unit.unit_group:
            availability, created = UnitGroupAvailability.objects.get_or_create(
                unit_group=unit.unit_group,
                defaults={
                    'total_units': unit.unit_group.capacity,
                    'available_units': 1,
                    'occupied_units': 0
                }
            )
            
            if not created:
                availability.available_units += 1
                availability.occupied_units = max(0, availability.occupied_units - 1)
                availability.save()

        # 3. Restore Listing status
        Listing.objects.filter(unit=unit, status='unavailable').update(status='active')

    @staticmethod
    def get_availability_summary(unit_group) -> dict:
        """
        Returns a formatted summary of availability for frontend display (e.g., "3 units remaining").
        """
        availability, created = UnitGroupAvailability.objects.get_or_create(
            unit_group=unit_group,
            defaults={
                'total_units': unit_group.capacity,
                'available_units': unit_group.capacity,
                'occupied_units': 0
            }
        )
        
        return {
            'total_units': availability.total_units,
            'available_units': availability.available_units,
            'occupied_units': availability.occupied_units,
            'is_visible': availability.is_marketplace_visible,
            'availability_text': availability.get_availability_text()
        }