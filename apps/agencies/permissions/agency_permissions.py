from rest_framework import permissions
from django.apps import apps
from ..utils.role_helpers import has_permission, get_effective_permissions

class IsAgencyAdmin(permissions.BasePermission):
    """
    Allows access only to users who are primary directors or have an 'operations_admin' 
    or 'property_manager' role within the agency.
    """
    def has_object_permission(self, request, view, obj):
        # obj can be the Agency instance or a model linked to it
        agency = getattr(obj, 'agency', obj)
        
        if not request.user.is_authenticated:
            return False
            
        # Check if user is a verified director of this agency
        is_director = agency.directors.filter(
            user=request.user, 
            verification_status='verified'
        ).exists()
        
        if is_director:
            return True
            
        # Check if user is an admin/manager staff member
        AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
        staff = AgencyStaff.objects.filter(
            agency=agency, 
            user=request.user, 
            status='active'
        ).first()
        
        if staff and staff.role in ['operations_admin', 'property_manager']:
            return True
            
        return False


class HasAgencyPermission(permissions.BasePermission):
    """
    Custom permission to check if the user's staff role grants them a specific permission key.
    Usage: permission_classes = [HasAgencyPermission('can_manage_tenants')]
    """
    def __init__(self, permission_key):
        self.permission_key = permission_key

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
        staff = AgencyStaff.objects.filter(
            user=request.user, 
            status='active'
        ).first()
        
        if not staff:
            return False
            
        # For global actions, check base role permissions
        return has_permission(staff, self.permission_key)

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
            
        AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
        staff = AgencyStaff.objects.filter(
            user=request.user, 
            status='active'
        ).first()
        
        if not staff:
            return False
            
        # If the object is a property or linked to a property, check property-specific overrides
        property_ref = getattr(obj, 'property_ref', getattr(obj, 'property', None))
        return has_permission(staff, self.permission_key, property_ref)


class IsDelegatedPropertyManager(permissions.BasePermission):
    """
    Ensures the user is an active staff member of the agency that currently 
    holds active delegation rights to the specific property.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
            
        # obj should be a DelegatedProperty or a Property
        if hasattr(obj, 'agency'):
            agency = obj.agency
            property_ref = obj.property_ref
        else:
            # If obj is a Property, we need to check if the user's agency has delegation
            property_ref = obj
            DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
            AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
            
            staff = AgencyStaff.objects.filter(user=request.user, status='active').first()
            if not staff:
                return False
                
            has_delegation = DelegatedProperty.objects.filter(
                property_ref=property_ref,
                agency=staff.agency,
                status='active'
            ).exists()
            return has_delegation

        # Check if user belongs to this agency and is active
        AgencyStaff = apps.get_model('agencies', 'AgencyStaff')
        return AgencyStaff.objects.filter(
            agency=agency,
            user=request.user,
            status='active'
        ).exists()