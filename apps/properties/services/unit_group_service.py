import math

from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import UnitGroup, Unit
from ..models.enums import UnitStatus
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
    def update_unit_group(instance: UnitGroup, update_data: dict) -> UnitGroup:
        for key, value in update_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

    # ✅ NEW: DELETION LOGIC WITH STRICT BUSINESS RULES
    @staticmethod
    @transaction.atomic
    def delete_unit_group(unit_group: UnitGroup) -> None:
        """
        Deletes a unit group and all its associated available/reserved units.
        CRITICAL RULE: Cannot delete if ANY unit in the group is occupied.
        """
        # 1. Check for occupied units in this group
        occupied_units_exist = Unit.objects.filter(
            unit_group=unit_group, 
            status=UnitStatus.OCCUPIED
        ).exists()
        
        if occupied_units_exist:
            raise ValidationError(
                "Cannot delete this Unit Group because it contains occupied units. "
                "Terminate all tenancies in this group first."
            )
        
        # 2. Double-check active tenancy records linked to this group's units
        from apps.tenancy.models.tenancy import Tenancy
        active_tenancies_exist = Tenancy.objects.filter(
            unit__unit_group=unit_group, 
            status='active'
        ).exists()
        
        if active_tenancies_exist:
            raise ValidationError(
                "Cannot delete this Unit Group because it has active tenancy records."
            )

        # 3. Safe to delete (Django will cascade delete the non-occupied units)
        unit_group.delete()

    @staticmethod
    @transaction.atomic
    def generate_units_from_group(unit_group: UnitGroup, user) -> list:
        property_obj = unit_group.property
        PropertyValidationService.validate_unit_generation_capacity(property_obj, unit_group.capacity)
        
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

        units_per_floor = math.ceil(unit_group.capacity / total_floors)
        created_units = []
        global_sequence = 1 
        
        for current_floor in range(start_floor, end_floor + 1):
            if current_floor == end_floor:
                units_to_create_here = unit_group.capacity - (global_sequence - 1)
            else:
                units_to_create_here = units_per_floor
                
            if units_to_create_here <= 0:
                break

            for _ in range(units_to_create_here):
                unit_code = generate_unit_code(
                    property_id=property_obj.id,
                    group_prefix=unit_group.name,
                    floor_number=current_floor,
                    sequence=global_sequence
                )
                
                unit = Unit.objects.create(
                    property_ref=property_obj, 
                    unit_group=unit_group,
                    unit_code=unit_code,
                    unit_type=unit_group.unit_type,
                    floor_number=current_floor, 
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

    @staticmethod
    @transaction.atomic
    def finalize_property_unit_groups(property, user, groups_data: list) -> list:
        created_groups = []
        UnitGroup.objects.filter(property=property).delete()
        
        for group_data in groups_data:
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
            UnitGroupService.generate_units_from_group(group, user)
            created_groups.append(group)
            
        return created_groups