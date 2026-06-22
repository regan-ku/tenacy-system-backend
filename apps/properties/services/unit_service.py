from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Property, Unit, UnitGroup
from ..models.enums import UnitStatus, BillingCycle
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
        """
        Creates a single unit directly linked to the property. 
        Used for Mansions, Bungalows, Plots, etc.
        """
        # 1. Validate it's actually a single-unit property
        if not PropertyValidationService.should_skip_unit_group(property_obj):
            raise ValidationError(
                "This property type requires Unit Groups for bulk management. "
                "Please use the Unit Group generation workflow instead."
            )

        # 2. CRITICAL: Validate floor number against property floors
        PropertyValidationService.validate_floor_assignment(property_obj, floor_number)

        # 3. Validate billing cycle for this property type
        PropertyValidationService.validate_billing_cycle(property_obj.property_sub_type, billing_cycle)

        # 4. Generate unit code if not provided
        if not unit_code:
            unit_code = generate_unit_code(
                property_id=property_obj.id,
                group_prefix=property_obj.title.split()[0] if property_obj.title else "PROP",
                floor_number=floor_number,
                sequence=1
            )
            
        # ✅ FIX: Changed 'property=' to 'property_ref='
        if Unit.objects.filter(property_ref=property_obj, unit_code=unit_code).exists():
            raise ValidationError(f"Unit code '{unit_code}' already exists for this property.")

        # 5. Create the unit
        unit = Unit.objects.create(
            property_ref=property_obj, # ✅ FIX: Changed from property=
            unit_group=None, # Explicitly null for single-unit properties
            unit_code=unit_code,
            unit_type=unit_type,
            floor_number=floor_number,
            rent_amount=rent_amount,
            deposit_amount=deposit_amount,
            service_charge=service_charge,
            # ✅ FIX: Removed currency="KES" because it's not a DB column on the Unit model
            billing_cycle=billing_cycle,
            billing_date=billing_date,
            status=UnitStatus.AVAILABLE
        )
        return unit

    @staticmethod
    @transaction.atomic
    def update_unit(unit: Unit, update_data: dict) -> Unit:
        """
        Updates an individual unit, enforcing strict validation rules on the new data.
        """
        if 'floor_number' in update_data:
            # ✅ FIX: Changed unit.property to unit.property_ref
            PropertyValidationService.validate_floor_assignment(unit.property_ref, update_data['floor_number'])
            
        if 'billing_cycle' in update_data:
            # ✅ FIX: Changed unit.property to unit.property_ref
            PropertyValidationService.validate_billing_cycle(unit.property_ref.property_sub_type, update_data['billing_cycle'])
            
        for key, value in update_data.items():
            setattr(unit, key, value)
            
        unit.save()
        return unit

    @staticmethod
    @transaction.atomic
    def update_unit_status(unit: Unit, new_status: str) -> Unit:
        """
        Safely updates unit status (e.g., available -> occupied).
        """
        valid_statuses = [choice[0] for choice in UnitStatus.choices]
        if new_status not in valid_statuses:
            raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
        if new_status == UnitStatus.AVAILABLE and unit.status == UnitStatus.OCCUPIED:
            raise ValidationError("Cannot mark unit as available while it has an active tenancy. Terminate tenancy first.")
            
        unit.status = new_status
        unit.save(update_fields=['status'])
        return unit

    @staticmethod
    def get_unit_with_inheritance(unit: Unit) -> dict:
        """
        Returns unit data merged with inherited property rules for clean API serialization.
        """
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
            # ✅ FIX: Changed unit.property to unit.property_ref for inherited fields
            "allows_pets": unit.property_ref.allows_pets,
            "parking_spaces": unit.property_ref.parking_spaces,
            "property_has_internet": unit.property_ref.has_internet,
            "property_has_cctv": unit.property_ref.has_cctv,
        }