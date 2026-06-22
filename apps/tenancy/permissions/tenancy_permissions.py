from rest_framework import permissions
from django.apps import apps

class IsTenantOfUnit(permissions.BasePermission):
    """
    Ensures that a user can only access tenancy records for units they actually occupy.
    """
    def has_object_permission(self, request, view, obj):
        # obj can be Tenancy, Occupancy, or TenancyHistory
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.user
        return False


class IsPropertyManagerOrOwner(permissions.BasePermission):
    """
    Allows access only to the property owner (created_by) or the currently assigned manager/agency.
    """
    def has_object_permission(self, request, view, obj):
        # obj can be Tenancy, Transfer, or Termination
        property_obj = getattr(obj, 'property', None)
        if not property_obj:
            return False
            
        return (
            property_obj.created_by == request.user or
            property_obj.current_manager == request.user or
            request.user.role == 'admin'
        )


class CanApproveTenancyActions(permissions.BasePermission):
    """
    Ensures that only authorized personnel (Managers, Landlords, or delegated Agents) 
    can approve waivers, extensions, or terminations.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
            
        user = request.user
        return user.role in ['landlord', 'agency', 'agent', 'admin']

    def has_object_permission(self, request, view, obj):
        property_obj = getattr(obj, 'property', None)
        if not property_obj:
            return False
            
        # Admins and Landlords always have access
        if request.user.role in ['admin', 'landlord'] and property_obj.created_by == request.user:
            return True
            
        # Check agency/agent delegation
        if request.user.role in ['agency', 'agent']:
            DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
            return DelegatedProperty.objects.filter(
                property_ref=property_obj,
                agency__staff_members__user=request.user,
                status='active'
            ).exists()
            
        return False