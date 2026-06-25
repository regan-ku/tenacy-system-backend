from rest_framework import permissions
from ..models import Application

class IsApplicant(permissions.BasePermission):
    """Allows access only to the user who submitted the application."""
    def has_object_permission(self, request, view, obj):
        return obj.applicant == request.user


class IsAgentOrManager(permissions.BasePermission):
    """
    Allows access to Agents, Managers, Agencies, Landlords, and Admins for reviewing applications.
    """
    def has_permission(self, request, view):
        # ✅ CRITICAL FIX: Added 'agency' to the list of allowed roles
        return request.user.is_authenticated and request.user.role in ['agent', 'manager', 'landlord', 'admin', 'agency']

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # ✅ FIX: Safely get property object (handles 'property_ref' or 'property')
        property_obj = getattr(obj, 'property_ref', None) or getattr(obj, 'property', None)
        if not property_obj:
            return False
        
        # Landlords, Agencies, and Admins have overarching access
        if user.role in ['landlord', 'admin', 'agency']:
            return True
            
        # Managers must be the current manager of the property
        if user.role == 'manager' and getattr(property_obj, 'current_manager', None) == user:
            return True
            
        # Agents must be staff of the agency managing the property
        if user.role == 'agent':
            current_mgr = getattr(property_obj, 'current_manager', None)
            if current_mgr and current_mgr.role == 'agency':
                return True 
                
        return False


class CanApproveApplication(permissions.BasePermission):
    """
    Strict permission check for the APPROVE/REJECT/ESCALATE actions.
    """
    def has_permission(self, request, view):
        # ✅ FIX: Added has_permission to ensure the request isn't blocked early by DRF
        return request.user.is_authenticated and request.user.role in ['agent', 'manager', 'landlord', 'admin', 'agency']

    def has_object_permission(self, request, view, obj):
        user = request.user
        # ✅ FIX: Added 'agency' to the allowed roles
        return user.role in ['agent', 'manager', 'landlord', 'admin', 'agency']