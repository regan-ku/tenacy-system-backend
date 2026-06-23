from django.core.exceptions import ValidationError
from ..models import Property, Unit, UnitGroup
from ..models.enums import PropertySubType, BillingCycle

class PropertyValidationService:
    """
    Comprehensive validation engine for all property and unit operations.
    Prevents invalid data from ever reaching the database.
    """

    @staticmethod
    def validate_property_structure(property: Property):
        """Validates basic property constraints."""
        if property.total_units_capacity < 1:
            raise ValidationError("A property must have a capacity of at least 1 unit.")
        if property.number_of_floors < 1:
            raise ValidationError("A property must have at least 1 floor.")

    @staticmethod
    def validate_floor_assignment(property: Property, floor_number: int):
        """
        CRITICAL: Ensures a unit is not assigned to a floor higher than the property has.
        """
        if floor_number > property.number_of_floors:
            raise ValidationError(
                f"Invalid floor number. Cannot assign unit to floor {floor_number} "
                f"because the property only has {property.number_of_floors} floor(s)."
            )
        if floor_number < 0:
            raise ValidationError("Floor number cannot be negative. Use 0 for Ground floor.")

    @staticmethod
    def validate_unit_generation_capacity(property: Property, requested_quantity: int):
        """
        Ensures generating new units will not exceed the property's total capacity.
        """
        # ✅ FIX: Use explicit query to avoid related_name issues
        current_units_count = Unit.objects.filter(property_ref=property).count()
        if current_units_count + requested_quantity > property.total_units_capacity:
            raise ValidationError(
                f"Cannot generate {requested_quantity} units. Property capacity is {property.total_units_capacity}, "
                f"and {current_units_count} units already exist."
            )

    @staticmethod
    def validate_billing_cycle(property_sub_type: str, billing_cycle: str):
        """
        Ensures the billing cycle makes sense for the property type.
        """
        # ✅ CRITICAL FIX: Safely get enum values to prevent AttributeError 
        # if some choices (like VACATION_HOME) are missing in models.py
        hospitality_types = [
            getattr(PropertySubType, attr, None) 
            for attr in ['AIRBNB', 'HOTEL', 'GUEST_HOUSE', 'VACATION_HOME', 'HOLIDAY_COTTAGE', 'SERVICED_APARTMENT']
        ]
        hospitality_types = [val for val in hospitality_types if val is not None]

        short_billing_cycles = [
            getattr(BillingCycle, attr, None)
            for attr in ['DAILY', 'WEEKLY']
        ]
        short_billing_cycles = [val for val in short_billing_cycles if val is not None]
        
        # If it's hospitality, daily/weekly is allowed. Otherwise, enforce monthly+.
        if property_sub_type not in hospitality_types and billing_cycle in short_billing_cycles:
            raise ValidationError(
                f"Billing cycle '{billing_cycle}' is not valid for {property_sub_type}. "
                "Use Monthly, Quarterly, or Yearly for standard rentals."
            )

    @staticmethod
    def should_skip_unit_group(property: Property) -> bool:
        """
        Determines if the property onboarding should skip the Unit Group creation step.
        """
        # 1. Explicit flag from the frontend takes absolute precedence
        if property.is_single_unit_property:
            return True
            
        # ✅ FIX: Safely get enum values for land/plots to prevent AttributeErrors
        land_and_plot_subtypes = [
            getattr(PropertySubType, attr, None)
            for attr in ['RESIDENTIAL_PLOT', 'COMMERCIAL_LAND', 'AGRICULTURAL_LAND', 'LAND']
        ]
        land_and_plot_subtypes = [val for val in land_and_plot_subtypes if val is not None]
        
        return property.property_sub_type in land_and_plot_subtypes

    @staticmethod
    def validate_unit_group_creation(property: Property, unit_group_data: dict):
        """Validates unit group data before creation."""
        PropertyValidationService.validate_billing_cycle(
            property.property_sub_type, 
            unit_group_data.get('billing_cycle', 'monthly') # ✅ Used string literal to be safe
        )
        PropertyValidationService.validate_unit_generation_capacity(
            property, 
            unit_group_data.get('capacity', 1)
        )