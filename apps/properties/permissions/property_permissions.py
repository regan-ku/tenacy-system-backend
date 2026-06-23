from rest_framework import permissions
from django.apps import apps

def get_property_from_obj(obj):
    """
    Safely extracts the parent Property object from various model instances 
    (Property, Unit, UnitGroup, PropertyMedia).
    """
    # Unit and PropertyMedia use 'property_ref' as the FK name
    if hasattr(obj, 'property_ref'):
        return obj.property_ref
    
    # UnitGroup and DelegatedProperty use 'property' as the FK name
    if hasattr(obj, 'property'):
        return obj.property
    
    # If the object is already the Property itself
    if obj.__class__.__name__ == 'Property':
        return obj
        
    return None


class IsPropertyOwnerOrManager(permissions.BasePermission):
    """
    Allows access only to the user who created the property or the currently assigned manager.
    """
    def has_object_permission(self, request, view, obj):
        property_obj = get_property_from_obj(obj)
        if not property_obj:
            return False
            
        return (
            property_obj.created_by == request.user or
            property_obj.current_manager == request.user or
            getattr(request.user, 'role', '') == 'admin'
        )


class IsDelegatedAgencyStaff(permissions.BasePermission):
    """
    Allows access to agency staff members who have been explicitly assigned to this property 
    via the agencies.DelegatedProperty and AgencyStaff models.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
            
        property_obj = get_property_from_obj(obj)
        if not property_obj:
            return False
        
        AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
        DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
        
        # Check if user is an active staff member of an agency that manages this property
        # We try 'property' first, then fallback to 'property_ref' depending on your exact model definition
        delegation = DelegatedProperty.objects.filter(
            property=property_obj,
            agency__staff_members__user=request.user,
            agency__staff_members__status='active',
            status='active'
        ).first()
        
        if not delegation:
            delegation = DelegatedProperty.objects.filter(
                property_ref=property_obj,
                agency__staff_members__user=request.user,
                agency__staff_members__status='active',
                status='active'
            ).first()
        
        return delegation is not None


class IsMarketplaceReadOnly(permissions.BasePermission):
    """
    Allows public read-only access to properties/units that are published and available.
    Write operations are denied.
    """
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests to anyone
        if request.method in permissions.SAFE_METHODS:
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            property_obj = get_property_from_obj(obj)
            if not property_obj:
                return False
                
            # Ensure the property is actually published and active
            return property_obj.is_active and getattr(property_obj, 'is_published', False)
        return False