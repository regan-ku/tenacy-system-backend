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
            
        # Admin always has access
        if request.user.role == 'admin':
            return True
            
        # Property owner or current manager has access
        return (
            property_obj.created_by == request.user or
            property_obj.current_manager == request.user
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
        
        user = request.user
            
        # Admins always have access
        if user.role == 'admin':
            return True
        
        # Property owner (landlord) has access
        if property_obj.created_by == user:
            return True
        
        # Current manager has access (could be landlord or agency)
        if property_obj.current_manager == user:
            return True
            
        # Check if user is an agency owner or staff member with delegation
        if user.role in ['agency', 'agent']:
            try:
                Agency = apps.get_model('agencies', 'Agency')
                DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
                
                # Check if user owns an agency that has delegation
                user_agency = Agency.objects.filter(
                    created_by=user,
                    delegations__property_ref=property_obj,
                    delegations__status='active'
                ).exists()
                
                if user_agency:
                    return True
                
                # Check if user is a staff member of an agency with delegation
                is_delegated_staff = DelegatedProperty.objects.filter(
                    property_ref=property_obj,
                    agency__staff_members__user=user,
                    agency__staff_members__status='active',
                    status='active'
                ).exists()
                
                return is_delegated_staff
            except Exception as e:
                print(f"Error checking agency delegation: {e}")
                return False
            
        return False