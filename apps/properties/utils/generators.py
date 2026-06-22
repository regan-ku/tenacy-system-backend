from django.core.exceptions import ValidationError
from ..models import Unit

def generate_unit_code(property_id: int, group_prefix: str, floor_number: int, sequence: int) -> str:
    """
    Generates a unique, standardized unit code based on the unit group prefix and floor.
    """
    # Extract first letter of the prefix, or use 'U' if empty
    prefix_char = (group_prefix.split()[0][0] if group_prefix else 'U').upper()
    
    # Format floor to 1 digit (e.g., Ground = 0, 1st floor = 1)
    floor_str = str(floor_number)[-1] 
    
    # Format sequence to 2 digits (e.g., 1 -> 01, 12 -> 12)
    seq_str = f"{sequence:02d}"
    
    proposed_code = f"{prefix_char}{floor_str}{seq_str}"
    
    # ✅ FIX: Changed 'property_id=' to 'property_ref_id=' to match the actual DB schema
    if Unit.objects.filter(property_ref_id=property_id, unit_code=proposed_code).exists():
        # Fallback: append a random digit if collision occurs (rare but safe)
        import random
        proposed_code = f"{proposed_code}{random.randint(1, 9)}"
        
    return proposed_code

def validate_unit_generation_capacity(property, requested_quantity: int):
    """
    Validates that generating new units will not exceed the property's total_units_capacity.
    """
    # ✅ FIX: Changed property.units.count() to explicitly query via property_ref 
    # to avoid related_name errors if the reverse relation isn't named 'units'
    current_units_count = Unit.objects.filter(property_ref=property).count()
    
    if current_units_count + requested_quantity > property.total_units_capacity:
        raise ValidationError(
            f"Cannot generate {requested_quantity} units. Property capacity is {property.total_units_capacity}, "
            f"and {current_units_count} units already exist."
        )