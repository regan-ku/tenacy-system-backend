from rest_framework import permissions
from django.apps import apps

class IsPropertyOwnerOrManager(permissions.BasePermission):
    """
    Allows access only to the user who created the property or the currently assigned manager.
    """
    def has_object_permission(self, request, view, obj):
        # obj can be a Property, Unit, or UnitGroup
        property_obj = getattr(obj, 'property', obj)
        
        return (
            property_obj.created_by == request.user or
            property_obj.current_manager == request.user or
            request.user.role == 'admin'
        )


class IsDelegatedAgencyStaff(permissions.BasePermission):
    """
    Allows access to agency staff members who have been explicitly assigned to this property 
    via the agencies.DelegatedProperty and AgencyStaff models.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
            
        property_obj = getattr(obj, 'property', obj)
        
        # Check if user is an active staff member of an agency that manages this property
        AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
        DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
        
        # Find if the user's agency has an active delegation for this property
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
            # Ensure the property is actually published and active
            property_obj = getattr(obj, 'property', obj)
            return property_obj.is_active and getattr(property_obj, 'is_marketplace_ready', True)
        return False