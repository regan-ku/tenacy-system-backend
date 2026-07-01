from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
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
        return property_obj

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
        Enforces strict business rules:
        - Landlords can ONLY assign Caretakers.
        - Agencies can assign Agents, Caretakers, and Property Managers.
        - Tenants can be assigned as Caretakers (Resident Caretaker).
        """
        from ..models.staff_assignment import PropertyStaffAssignment
        from apps.agencies.models.delegated_property import DelegatedProperty
        from apps.agencies.models.agency import Agency
        
        # 1. Determine the Assignment Source (Landlord vs Agency)
        assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.LANDLORD
        assigned_by_agency = None
        
        # Check if the property is actively delegated to an agency
        active_delegation = DelegatedProperty.objects.filter(
            property_ref=property_obj, 
            status=DelegatedProperty.Status.ACTIVE
        ).first()
        
        if active_delegation:
            assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.AGENCY
            assigned_by_agency = active_delegation.agency
            
            # If delegated, only Agency staff (or the agency owner) can assign staff
            if assigning_user.role not in ['agency', 'agent', 'property_manager', 'admin']:
                raise ValidationError("This property is fully delegated. Only the managing agency can assign staff.")
                
        elif assigning_user.role == 'agency':
            # ✅ FIX: If the user is an Agency and they own/manage the property directly (no delegation record needed)
            assigned_by_entity_type = PropertyStaffAssignment.AssignmentSource.AGENCY
            
            # Find the agency owned by this user
            agency = Agency.objects.filter(
                Q(created_by=assigning_user) | 
                Q(directors__user=assigning_user) |
                Q(contact_email=assigning_user.email)
            ).first()
            
            assigned_by_agency = agency
            
        else:
            # Self-managed by Landlord
            if property_obj.created_by != assigning_user and assigning_user.role != 'admin':
                raise ValidationError("You do not have permission to assign staff to this property.")

        # 2. Enforce Role Restrictions
        if assigned_by_entity_type == PropertyStaffAssignment.AssignmentSource.LANDLORD:
            if operational_role != PropertyStaffAssignment.OperationalRole.CARETAKER:
                raise ValidationError("Landlords can only assign Caretakers to their properties.")
        
        # 3. Handle Tenant as Caretaker (Resident Caretaker)
        if user_to_assign.role == 'tenant':
            if operational_role != PropertyStaffAssignment.OperationalRole.CARETAKER:
                raise ValidationError("Tenants can only be assigned as Caretakers (Resident Caretaker).")

        # 4. Create or Reactivate the Assignment
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
            # Reactivate if previously terminated
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
            
        # Permission check
        if assignment.assigned_by_entity_type == PropertyStaffAssignment.AssignmentSource.LANDLORD:
            if property_obj.created_by != assigning_user and assigning_user.role != 'admin':
                raise ValidationError("Only the property owner can terminate this assignment.")
        else:
            if assigning_user.role not in ['agency', 'admin']:
                raise ValidationError("Only the managing agency can terminate this assignment.")
                
        assignment.terminate()
        return assignment