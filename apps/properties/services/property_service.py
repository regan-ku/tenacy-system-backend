from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from ..models import Property, Location, Unit, UnitGroup
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

        # ✅ CRITICAL FIX: Determine initial active state
        # If it's a single unit property, it doesn't need a complex unit generation wizard.
        # We can consider it "Active" immediately after basic creation.
        initial_active_state = True if is_single_unit else False

        property_obj = Property.objects.create(
            created_by=created_by_user,
            current_manager=created_by_user,
            location=location,
            is_single_unit_property=is_single_unit,
            is_active=initial_active_state, # ✅ Set based on property type
            **kwargs
        )
        
        PropertyValidationService.validate_property_structure(property_obj)
        return property_obj

    @staticmethod
    @transaction.atomic
    def finalize_property_wizard(property: Property, user) -> Property:
        """
        Called by the frontend ONLY when the user finishes the Unit Group / Media wizard.
        Flips the property from 'Draft' to 'Active' so it can be published.
        """
        if property.is_active:
            return property # Already active

        # Safety check: Ensure they actually created units before activating
        if not property.is_single_unit_property and not property.unit_groups.exists():
            raise ValidationError("Cannot activate property. Please create at least one Unit Group first.")

        property.is_active = True
        property.save(update_fields=['is_active', 'updated_at'])
        
        return property

    @staticmethod
    @transaction.atomic
    def update_property(property: Property, user, update_data: dict) -> Property:
        """
        Updates property details. Enforces strict structural validations.
        """
        if 'number_of_floors' in update_data:
            new_floors = update_data['number_of_floors']
            units_above = Unit.objects.filter(property_ref=property, floor_number__gt=new_floors).exists()
            if units_above:
                raise ValidationError(
                    f"Cannot reduce floors to {new_floors} because there are existing units on higher floors."
                )

        if 'total_units_capacity' in update_data:
            existing_units_count = Unit.objects.filter(property_ref=property).count()
            new_capacity = update_data['total_units_capacity']
            if new_capacity < existing_units_count:
                raise ValidationError(
                    f"Cannot reduce capacity to {new_capacity} because {existing_units_count} units already exist."
                )
        
        for key, value in update_data.items():
            setattr(property, key, value)
            
        property.save()
        return property

    # ==========================================
    # ✅ STAFF ASSIGNMENT LOGIC
    # ==========================================

    @staticmethod
    @transaction.atomic
    def assign_staff_to_property(property_obj: Property, user_to_assign, assigning_user, operational_role: str, notes: str = None):
        """
        Assigns a user (Staff or Tenant) to a property with a specific operational role.
        """
        from ..models.staff_assignment import PropertyStaffAssignment
        from apps.agencies.models.delegated_property import DelegatedProperty
        from apps.agencies.models.agency import Agency
        
        # 1. Determine the Assignment Source (Landlord vs Agency)
        assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.LANDLORD
        assigned_by_agency = None
        
        active_delegation = DelegatedProperty.objects.filter(
            property_ref=property_obj, 
            status=DelegatedProperty.Status.ACTIVE
        ).first()
        
        if active_delegation:
            assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.AGENCY
            assigned_by_agency = active_delegation.agency
            
            if assigning_user.role not in ['agency', 'agent', 'property_manager', 'admin']:
                raise ValidationError("This property is fully delegated. Only the managing agency can assign staff.")
                
        elif assigning_user.role == 'agency':
            assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.AGENCY
            agency = Agency.objects.filter(
                Q(created_by=assigning_user) | 
                Q(directors__user=assigning_user) |
                Q(contact_email=assigning_user.email)
            ).first()
            assigned_by_agency = agency
        else:
            if property_obj.created_by != assigning_user and assigning_user.role != 'admin':
                raise ValidationError("You do not have permission to assign staff to this property.")

        # 2. Enforce Role Restrictions
        if assigned_by_entity_type == PropertyStaffAssignment.AssignmentSource.LANDLORD:
            if operational_role != PropertyStaffAssignment.OperationalRole.CARETAKER:
                raise ValidationError("Landlords can only assign Caretakers to their properties.")
        
        if user_to_assign.role == 'tenant':
            if operational_role != PropertyStaffAssignment.OperationalRole.CARETAKER:
                raise ValidationError("Tenants can only be assigned as Caretakers (Resident Caretaker).")

        # 3. Create or Reactivate the Assignment
        assignment, created = PropertyStaffAssignment.objects.get_or_create(
            property=property_obj,
            user=user_to_assign,
            operational_role=operational_role,
            defaults={
                'assigned_by_entity_type': assigned_by_entity_type,
                'assigned_by_agency': assigned_by_agency,
                'is_active': True,
                'notes': notes
            }
        )
        
        if not created and not assignment.is_active:
            assignment.is_active = True
            assignment.terminated_at = None
            assignment.assigned_by_entity_type = assigned_by_entity_type
            assignment.assigned_by_agency = assigned_by_agency
            assignment.notes = notes
            assignment.save()
            
        return assignment

    @staticmethod
    def get_property_staff(property_obj: Property):
        """Returns all active staff assignments for a property."""
        from ..models.staff_assignment import PropertyStaffAssignment
        return PropertyStaffAssignment.objects.filter(
            property=property_obj, 
            is_active=True
        ).select_related('user', 'user__profile', 'assigned_by_agency')

    @staticmethod
    @transaction.atomic
    def terminate_staff_assignment(property_obj: Property, user_to_remove, assigning_user):
        """Safely removes a staff member from a property."""
        from ..models.staff_assignment import PropertyStaffAssignment
        
        assignment = PropertyStaffAssignment.objects.filter(
            property=property_obj,
            user=user_to_remove,
            is_active=True
        ).first()
        
        if not assignment:
            raise ValidationError("This user is not actively assigned to this property.")
            
        if assignment.assigned_by_entity_type == PropertyStaffAssignment.AssignmentSource.LANDLORD:
            if property_obj.created_by != assigning_user and assigning_user.role != 'admin':
                raise ValidationError("Only the property owner can terminate this assignment.")
        else:
            if assigning_user.role not in ['agency', 'admin']:
                raise ValidationError("Only the managing agency can terminate this assignment.")
                
        assignment.terminate()
        return assignment