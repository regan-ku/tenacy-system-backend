from django.db import transaction
from django.utils import timezone
from ..models import Occupancy
from apps.properties.models import Unit
from apps.marketplace.models import UnitGroupAvailability, Listing

class OccupancyService:
    """
    Manages real-time unit occupancy state and synchronizes it 
    with the public marketplace availability.
    """

    @staticmethod
    @transaction.atomic
    def mark_unit_occupied(unit: Unit, tenant, tenancy):
        """
        Called when a tenancy becomes ACTIVE.
        Removes the unit from marketplace availability.
        """
        # 1. Update Unit status
        unit.status = 'occupied'
        unit.save(update_fields=['status'])

        # 2. Create or update Occupancy record
        occupancy, created = Occupancy.objects.update_or_create(
            unit=unit,
            defaults={
                'is_occupied': True,
                'current_tenant': tenant,
                'active_tenancy': tenancy,
                'occupancy_start_date': timezone.now().date()
            }
        )

        # 3. Sync with Marketplace Unit Group Availability
        if unit.unit_group:
            availability, _ = UnitGroupAvailability.objects.get_or_create(
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
                availability.save() # The save() method auto-hides if available_units == 0

            # 4. Update specific unit listing status in marketplace
            Listing.objects.filter(unit=unit, status='active').update(status='unavailable')

    @staticmethod
    @transaction.atomic
    def mark_unit_vacant(unit: Unit, tenancy):
        """
        Called when a tenancy is TERMINATED, EXPIRED, or TRANSFERRED.
        Restores the unit to marketplace availability.
        """
        # 1. Update Unit status
        unit.status = 'available'
        unit.save(update_fields=['status'])

        # 2. Update Occupancy record
        try:
            occupancy = Occupancy.objects.get(unit=unit)
            occupancy.is_occupied = False
            occupancy.current_tenant = None
            occupancy.active_tenancy = None
            occupancy.occupancy_end_date = timezone.now().date()
            occupancy.save()
        except Occupancy.DoesNotExist:
            pass

        # 3. Sync with Marketplace Unit Group Availability
        if unit.unit_group:
            try:
                availability = UnitGroupAvailability.objects.get(unit_group=unit.unit_group)
                availability.available_units += 1
                availability.occupied_units = max(0, availability.occupied_units - 1)
                availability.save() # The save() method auto-restores visibility if available_units > 0
            except UnitGroupAvailability.DoesNotExist:
                pass

        # 4. Restore specific unit listing status in marketplace
        Listing.objects.filter(unit=unit, status='unavailable').update(status='active')