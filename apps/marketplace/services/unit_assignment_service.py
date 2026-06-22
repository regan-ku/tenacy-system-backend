import random
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.properties.models import Unit, UnitGroup
from ..models import UnitGroupAvailability

class UnitAssignmentService:
    """
    Handles random unit assignment from unit groups during the application process.
    Enforces the rule: Backend picks the specific unit, user can only specify preferred floor.
    """

    @staticmethod
    @transaction.atomic
    def assign_random_unit(unit_group: UnitGroup, preferred_floor: int = None) -> Unit:
        """
        Randomly assigns an available unit from the specified unit group.
        """
        # 1. Get all currently available units in this group
        available_units = Unit.objects.filter(
            unit_group=unit_group,
            status='available'
        )
        
        if not available_units.exists():
            raise ValidationError("No available units in this unit group.")
        
        # 2. If user specified a preferred floor, validate and filter
        if preferred_floor is not None:
            # Validate floor against property limits
            if preferred_floor < 0 or preferred_floor > unit_group.property.number_of_floors:
                raise ValidationError(
                    f"Invalid floor. Property only has floors 0 to {unit_group.property.number_of_floors}."
                )
            
            # Filter available units by preferred floor
            floor_units = available_units.filter(floor_number=preferred_floor)
            if floor_units.exists():
                available_units = floor_units
            else:
                # Fallback: If no units on preferred floor, inform user or assign randomly from any floor
                # For now, we proceed with any available floor, but you can raise ValidationError here if strict
                pass 
        
        # 3. Randomly select one unit from the filtered queryset
        assigned_unit = random.choice(list(available_units))
        
        # 4. Temporarily mark as reserved (pending application approval)
        # Note: Actual 'occupied' status is handled by AvailabilityService when Tenancy is activated
        return assigned_unit

    @staticmethod
    def validate_application_eligibility(unit_group: UnitGroup):
        """
        Checks if a unit group is eligible to receive new applications.
        """
        summary = UnitGroupAvailability.objects.filter(unit_group=unit_group).first()
        if not summary or summary.available_units == 0:
            raise ValidationError("This unit group is fully occupied and not accepting applications.")
        return True