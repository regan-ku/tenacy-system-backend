from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Property, Unit, UnitGroup
from ..models.enums import UnitStatus
from .validation_service import PropertyValidationService
from ..utils.generators import generate_unit_code

class UnitService:
    """
    Manages individual Unit lifecycle, especially for single-unit properties 
    that bypass the Unit Group bulk generation workflow, and handles status updates.
    """

    @staticmethod
    @transaction.atomic
    def create_single_unit(
        property_obj: Property, 
        unit_type: str, 
        floor_number: int, 
        rent_amount: float, 
        deposit_amount: float, 
        service_charge: float,
        billing_cycle: str,
        billing_date: int,
        unit_code: str = None
    ) -> Unit:
        if not PropertyValidationService.should_skip_unit_group(property_obj):
            raise ValidationError("This property type requires Unit Groups for bulk management.")

        # ✅ CRITICAL FIX: Validate capacity before creating (should be 1 for single units)
        PropertyValidationService.validate_unit_generation_capacity(property_obj, 1)

        PropertyValidationService.validate_floor_assignment(property_obj, floor_number)
        PropertyValidationService.validate_billing_cycle(property_obj.property_sub_type, billing_cycle)

        if not unit_code:
            unit_code = generate_unit_code(
                property_id=property_obj.id,
                group_prefix=property_obj.title.split()[0] if property_obj.title else "PROP",
                floor_number=floor_number,
                sequence=1
            )
            
        if Unit.objects.filter(property_ref=property_obj, unit_code=unit_code).exists():
            raise ValidationError(f"Unit code '{unit_code}' already exists for this property.")

        unit = Unit.objects.create(
            property_ref=property_obj,
            unit_group=None,
            unit_code=unit_code,
            unit_type=unit_type,
            floor_number=floor_number,
            rent_amount=rent_amount,
            deposit_amount=deposit_amount,
            service_charge=service_charge,
            billing_cycle=billing_cycle,
            billing_date=billing_date,
            status=UnitStatus.AVAILABLE
        )
        return unit

    @staticmethod
    @transaction.atomic
    def create_unit_in_group(property_obj: Property, unit_group: UnitGroup, floor_number: int) -> Unit:
        """
        Creates a single unit within an existing Unit Group, inheriting all pricing and billing rules.
        """
        # ✅ CRITICAL FIX: Validate that adding 1 unit won't exceed the property's total capacity
        PropertyValidationService.validate_unit_generation_capacity(property_obj, 1)

        # 1. Validate floor number against property floors
        PropertyValidationService.validate_floor_assignment(property_obj, floor_number)

        # 2. Generate unique unit code
        existing_count = Unit.objects.filter(property_ref=property_obj).count()
        sequence = existing_count + 1
        
        unit_code = generate_unit_code(
            property_id=property_obj.id,
            group_prefix=unit_group.name,
            floor_number=floor_number,
            sequence=sequence
        )
        
        # Fallback if code somehow already exists
        if Unit.objects.filter(property_ref=property_obj, unit_code=unit_code).exists():
            unit_code = f"{unit_code}-{sequence}"

        # 3. Create the unit inheriting from the group
        unit = Unit.objects.create(
            property_ref=property_obj,
            unit_group=unit_group,
            unit_code=unit_code,
            unit_type=unit_group.unit_type,
            floor_number=floor_number,
            rent_amount=unit_group.base_rent_amount,
            deposit_amount=unit_group.deposit_amount,
            service_charge=unit_group.service_charge,
            billing_cycle=unit_group.billing_cycle,
            billing_date=unit_group.billing_date,
            status=UnitStatus.AVAILABLE
        )
        return unit

    @staticmethod
    @transaction.atomic
    def update_unit(unit: Unit, update_data: dict) -> Unit:
        if 'floor_number' in update_data:
            PropertyValidationService.validate_floor_assignment(unit.property_ref, update_data['floor_number'])
            
        if 'billing_cycle' in update_data:
            PropertyValidationService.validate_billing_cycle(unit.property_ref.property_sub_type, update_data['billing_cycle'])
            
        for key, value in update_data.items():
            setattr(unit, key, value)
            
        unit.save()
        return unit

    @staticmethod
    @transaction.atomic
    def update_unit_status(unit: Unit, new_status: str) -> Unit:
        valid_statuses = [choice[0] for choice in UnitStatus.choices]
        if new_status not in valid_statuses:
            raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
        if new_status == UnitStatus.AVAILABLE and unit.status == UnitStatus.OCCUPIED:
            raise ValidationError("Cannot mark unit as available while it has an active tenancy. Terminate tenancy first.")
            
        unit.status = new_status
        unit.save(update_fields=['status'])
        return unit

    @staticmethod
    @transaction.atomic
    def delete_unit(unit: Unit) -> None:
        if unit.status == UnitStatus.OCCUPIED:
            raise ValidationError(
                "Cannot delete this unit because it is currently occupied. "
                "You must terminate the active tenancy first."
            )
        
        from apps.tenancy.models.tenancy import Tenancy
        active_tenancy_exists = Tenancy.objects.filter(unit=unit, status='active').exists()
        if active_tenancy_exists:
            raise ValidationError(
                "Cannot delete this unit because it has an active tenancy record in the system."
            )

        unit.delete()

    @staticmethod
    def get_unit_with_inheritance(unit: Unit) -> dict:
        return {
            "unit_id": unit.id,
            "unit_code": unit.unit_code,
            "unit_type": unit.unit_type,
            "floor_number": unit.floor_number,
            "rent_amount": unit.rent_amount,
            "deposit_amount": unit.deposit_amount,
            "service_charge": unit.service_charge,
            "billing_cycle": unit.billing_cycle,
            "billing_date": unit.billing_date,
            "status": unit.status,
            "allows_pets": unit.property_ref.allows_pets,
            "parking_spaces": unit.property_ref.parking_spaces,
            "property_has_internet": unit.property_ref.has_internet,
            "property_has_cctv": unit.property_ref.has_cctv,
        }