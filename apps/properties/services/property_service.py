# from django.db import transaction
# from django.core.exceptions import ValidationError
# from ..models import Property, Location, Unit
# from .validation_service import PropertyValidationService

# class PropertyService:
#     """
#     Core business logic for Property lifecycle management.
#     """

#     @staticmethod
#     @transaction.atomic
#     def create_property(created_by_user, location_data: dict, **kwargs) -> Property:
#         is_single_unit_property = kwargs.pop('is_single_unit_property', False)
#         location = Location.objects.create(**location_data)
        
#         is_single_unit = PropertyValidationService.should_skip_unit_group(
#             type('Property', (), {'is_single_unit_property': is_single_unit_property, 
#                                   'property_sub_type': kwargs.get('property_sub_type', '')})
#         )

#         property_obj = Property.objects.create(
#             created_by=created_by_user,
#             current_manager=created_by_user,
#             location=location,
#             is_single_unit_property=is_single_unit,
#             **kwargs
#         )
        
#         PropertyValidationService.validate_property_structure(property_obj)
#         return property_obj

#     @staticmethod
#     @transaction.atomic
#     def update_property(property: Property, user, update_data: dict) -> Property:
#         """
#         Updates property details. Enforces strict structural validations and marketplace sync.
#         """
#         # 1. VALIDATE FLOOR REDUCTION
#         if 'number_of_floors' in update_data:
#             new_floors = update_data['number_of_floors']
#             units_above = Unit.objects.filter(property_ref=property, floor_number__gt=new_floors).exists()
#             if units_above:
#                 raise ValidationError(
#                     f"Cannot reduce floors to {new_floors} because there are existing units on higher floors."
#                 )

#         # 2. VALIDATE CAPACITY REDUCTION
#         if 'total_units_capacity' in update_data:
#             existing_units_count = Unit.objects.filter(property_ref=property).count()
#             new_capacity = update_data['total_units_capacity']
#             if new_capacity < existing_units_count:
#                 raise ValidationError(
#                     f"Cannot reduce capacity to {new_capacity} because {existing_units_count} units already exist."
#                 )
        
#         # 3. Apply updates to the property instance
#         for key, value in update_data.items():
#             setattr(property, key, value)
            
#         # Save to database
#         property.save()
        
#         # 4. ✅ MARKETPLACE SYNC (PUBLISH / UNPUBLISH)
#         is_published = getattr(property, 'is_published', False)
#         is_active = getattr(property, 'is_active', True)
        
#         # Import the newly fixed PublishingService
#         from apps.marketplace.services.publishing_service import PublishingService
        
#         if is_published and is_active:
#             # This will now actually create the Listing records!
#             PublishingService.publish_property(property, user)
#         else:
#             # This will hide the listings if unchecked
#             PublishingService.unpublish_property(property)
                
#         return property



from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Property, Location, Unit
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
        
        # ✅ NOTE: Because we used Property.objects.create(), the post_save signal 
        # will automatically fire and publish it if is_published=True was passed in kwargs!
        
        return property_obj

    @staticmethod
    @transaction.atomic
    def update_property(property: Property, user, update_data: dict) -> Property:
        """
        Updates property details. Enforces strict structural validations.
        Marketplace sync is now handled automatically by the Property post_save signal.
        """
        # 1. VALIDATE FLOOR REDUCTION
        if 'number_of_floors' in update_data:
            new_floors = update_data['number_of_floors']
            units_above = Unit.objects.filter(property_ref=property, floor_number__gt=new_floors).exists()
            if units_above:
                raise ValidationError(
                    f"Cannot reduce floors to {new_floors} because there are existing units on higher floors."
                )

        # 2. VALIDATE CAPACITY REDUCTION
        if 'total_units_capacity' in update_data:
            existing_units_count = Unit.objects.filter(property_ref=property).count()
            new_capacity = update_data['total_units_capacity']
            if new_capacity < existing_units_count:
                raise ValidationError(
                    f"Cannot reduce capacity to {new_capacity} because {existing_units_count} units already exist."
                )
        
        # 3. Apply updates to the property instance
        for key, value in update_data.items():
            setattr(property, key, value)
            
        # 4. Save to database 
        # ✅ The post_save signal will automatically trigger PublishingService!
        property.save()
                
        return property