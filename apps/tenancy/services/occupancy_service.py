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
        # ✅ CRITICAL FIX: Direct QuerySet update prevents stale instance issues
        # Guarantees Django Admin and frontend see the change immediately
        Unit.objects.filter(id=unit.id).update(status='occupied')

        # 2. Create or update Occupancy record
        Occupancy.objects.update_or_create(
            unit_id=unit.id,
            defaults={
                'is_occupied': True,
                'current_tenant': tenant,
                'active_tenancy': tenancy,
                'occupancy_start_date': timezone.now().date()
            }
        )

        # 3. Sync with Marketplace Unit Group Availability
        if unit.unit_group:
            # ✅ FIX: Use live DB counts instead of incremental math to prevent drift
            available_count = Unit.objects.filter(
                unit_group=unit.unit_group, 
                status='available'
            ).count()
            occupied_count = unit.unit_group.capacity - available_count
            
            UnitGroupAvailability.objects.update_or_create(
                unit_group=unit.unit_group,
                defaults={
                    'total_units': unit.unit_group.capacity,
                    'available_units': max(0, available_count),
                    'occupied_units': max(0, occupied_count)
                }
            )

            # 4. Hide listing if fully occupied
            if available_count == 0:
                Listing.objects.filter(
                    unit_group=unit.unit_group, 
                    status='active'
                ).update(status='unavailable')

    @staticmethod
    @transaction.atomic
    def mark_unit_vacant(unit: Unit, tenancy):
        """
        Called when a tenancy is TERMINATED, EXPIRED, or TRANSFERRED.
        Restores the unit to marketplace availability.
        """
        # ✅ CRITICAL FIX: Direct QuerySet update
        Unit.objects.filter(id=unit.id).update(status='available')

        # 2. Update Occupancy record
        Occupancy.objects.filter(unit_id=unit.id).update(
            is_occupied=False,
            current_tenant=None,
            active_tenancy=None,
            occupancy_end_date=timezone.now().date()
        )

        # 3. Sync with Marketplace Unit Group Availability
        if unit.unit_group:
            try:
                # ✅ FIX: Live DB counts prevent drift
                available_count = Unit.objects.filter(
                    unit_group=unit.unit_group, 
                    status='available'
                ).count()
                occupied_count = unit.unit_group.capacity - available_count
                
                UnitGroupAvailability.objects.update_or_create(
                    unit_group=unit.unit_group,
                    defaults={
                        'total_units': unit.unit_group.capacity,
                        'available_units': max(0, available_count),
                        'occupied_units': max(0, occupied_count)
                    }
                )

                # Restore listing visibility if units are available
                if available_count > 0:
                    Listing.objects.filter(
                        unit_group=unit.unit_group, 
                        status='unavailable'
                    ).update(status='active')
            except Exception as e:
                # Failsafe: marketplace sync won't block occupancy release
                print(f"⚠️ Marketplace sync failed for unit {unit.id}: {e}")