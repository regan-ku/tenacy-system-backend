import math

from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import UnitGroup, Unit
from ..utils.generators import generate_unit_code, validate_unit_generation_capacity
from .validation_service import PropertyValidationService

class UnitGroupService:
    """
    Manages Unit Groups and the bulk generation of individual Units.
    """

    @staticmethod
    @transaction.atomic
    def create_unit_group(property, name: str, unit_type: str, floor_range: str, 
                          billing_cycle: str, billing_date: int, base_rent_amount: float, 
                          deposit_amount: float, service_charge: float, capacity: int, **kwargs) -> UnitGroup:
        """
        Creates a unit group template. Does not generate units yet.
        """
        # Validate capacity against property limits
        validate_unit_generation_capacity(property, capacity)
        
        return UnitGroup.objects.create(
            property=property,
            name=name,
            unit_type=unit_type,
            floor_range=floor_range,
            billing_cycle=billing_cycle,
            billing_date=billing_date,
            base_rent_amount=base_rent_amount,
            deposit_amount=deposit_amount,
            service_charge=service_charge,
            capacity=capacity,
            **kwargs
        )

    @staticmethod
    @transaction.atomic
    def generate_units_from_group(unit_group: UnitGroup, user) -> list:
        """
        Bulk generates individual Unit records based on the Unit Group template.
        ✅ UPDATED: Now intelligently distributes units across the defined floor range.
        """
        property_obj = unit_group.property
        
        # 1. Validate generation won't exceed capacity
        PropertyValidationService.validate_unit_generation_capacity(property_obj, unit_group.capacity)
        
        # 2. Parse floor range (e.g., "1-3" -> start=1, end=3. Or "Ground" -> start=0, end=0)
        try:
            parts = unit_group.floor_range.split('-')
            start_floor = int(parts[0])
            end_floor = int(parts[1]) if len(parts) > 1 else start_floor
        except ValueError:
            start_floor = 1
            end_floor = 1
            
        total_floors = end_floor - start_floor + 1
        if total_floors <= 0:
            total_floors = 1

        # 3. Calculate distribution
        units_per_floor = math.ceil(unit_group.capacity / total_floors)
        
        created_units = []
        global_sequence = 1 # Ensures unique unit codes across all floors
        
        # 4. Loop through each floor and create the allocated units
        for current_floor in range(start_floor, end_floor + 1):
            # Calculate how many units to create on THIS specific floor
            if current_floor == end_floor:
                # On the last floor, create whatever is remaining to hit the exact capacity
                units_to_create_here = unit_group.capacity - (global_sequence - 1)
            else:
                units_to_create_here = units_per_floor
                
            if units_to_create_here <= 0:
                break

            for _ in range(units_to_create_here):
                # Generate unique code using utils
                unit_code = generate_unit_code(
                    property_id=property_obj.id,
                    group_prefix=unit_group.name,
                    floor_number=current_floor,
                    sequence=global_sequence
                )
                
                # Create Unit, inheriting financial and billing rules from the group
                unit = Unit.objects.create(
                    property_ref=property_obj, 
                    unit_group=unit_group,
                    unit_code=unit_code,
                    unit_type=unit_group.unit_type,
                    floor_number=current_floor, # ✅ Now correctly assigned per floor
                    rent_amount=unit_group.base_rent_amount,
                    deposit_amount=unit_group.deposit_amount,
                    service_charge=unit_group.service_charge,
                    billing_cycle=unit_group.billing_cycle,
                    billing_date=unit_group.billing_date,
                    status='available'
                )
                created_units.append(unit)
                global_sequence += 1
            
        return created_units

    # ✅🚨 NEW ARCHITECTURAL BRIDGE METHOD
    @staticmethod
    @transaction.atomic
    def finalize_property_unit_groups(property, user, groups_data: list) -> list:
        """
        ARCHITECTURAL BRIDGE: 
        Takes frontend Unit Group drafts, saves them to the DB, and immediately 
        generates the individual Unit records. This ensures Units exist in the DB 
        before the user proceeds to the Media Upload step.
        """
        created_groups = []
        
        # 1. Clear any existing draft groups for this property to prevent duplicates on resubmission
        UnitGroup.objects.filter(property=property).delete()
        
        # 2. Create each group and generate its units
        for group_data in groups_data:
            # Create the Unit Group record
            group = UnitGroup.objects.create(
                property=property,
                name=group_data.get('name'),
                description=group_data.get('description', ''),
                unit_type=group_data.get('unit_type'),
                floor_range=group_data.get('floor_range'),
                billing_cycle=group_data.get('billing_cycle', 'monthly'),
                billing_date=group_data.get('billing_date', 5),
                base_rent_amount=group_data.get('base_rent_amount'),
                service_charge=group_data.get('service_charge_amount', 0),
                deposit_amount=group_data.get('deposit_amount', 0),
                capacity=group_data.get('capacity'),
                allows_pets_override=group_data.get('allows_pets_override')
            )
            
            # ✅ CRITICAL: Immediately generate the individual units for this group
            UnitGroupService.generate_units_from_group(group, user)
            
            created_groups.append(group)
            
        return created_groups