from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Property, Location
from .validation_service import PropertyValidationService

class PropertyService:
    """
    Core business logic for Property lifecycle management.
    """

    @staticmethod
    @transaction.atomic
    def create_property(created_by_user, location_data: dict, **kwargs) -> Property:
        is_single_unit_property = kwargs.pop('is_single_unit_property', False)
        location = Location.objects.create(**location_data)
        
        is_single_unit = PropertyValidationService.should_skip_unit_group(
            type('Property', (), {'is_single_unit_property': is_single_unit_property, 
                                  'property_sub_type': kwargs.get('property_sub_type', '')})
        )

        property_obj = Property.objects.create(
            created_by=created_by_user,
            current_manager=created_by_user,
            location=location,
            is_single_unit_property=is_single_unit,
            **kwargs
        )
        
        PropertyValidationService.validate_property_structure(property_obj)
        return property_obj

    @staticmethod
    @transaction.atomic
    def update_property(property: Property, user, update_data: dict) -> Property:
        """
        Updates property details. Prevents unauthorized structural changes if units exist.
        """
        if 'total_units_capacity' in update_data:
            if update_data['total_units_capacity'] < property.units.count():
                raise ValidationError("Cannot reduce capacity below the number of existing units.")
        
        for key, value in update_data.items():
            setattr(property, key, value)
            
        property.save()
        
        # ✅🚨 AUTOMATIC MARKETPLACE BRIDGE:
        # If the property is marked as published and active, sync it to the marketplace automatically.
        if getattr(property, 'is_published', False) and property.is_active:
            try:
                from apps.marketplace.services.publishing_service import PublishingService
                PublishingService.publish_property(property, user)
            except Exception as e:
                # Log the error but don't crash the property update
                print(f"[Marketplace Sync Warning] {e}")
                
        return property