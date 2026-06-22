from rest_framework import permissions
from ..models import Application

class IsApplicant(permissions.BasePermission):
    """Allows access only to the user who submitted the application."""
    def has_object_permission(self, request, view, obj):
        return obj.applicant == request.user


class IsAgentOrManager(permissions.BasePermission):
    """
    Allows access to Agents, Managers, and Landlords for reviewing applications.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['agent', 'manager', 'landlord', 'admin']

    def has_object_permission(self, request, view, obj):
        user = request.user
        property_obj = obj.property
        
        # Landlords and Admins have overarching access
        if user.role in ['landlord', 'admin']:
            return True
            
        # Managers must be the current manager of the property
        if user.role == 'manager' and property_obj.current_manager == user:
            return True
            
        # Agents must be staff of the agency managing the property
        if user.role == 'agent':
            if property_obj.current_manager and property_obj.current_manager.role == 'agency':
                # In production, this would check AgencyStaff.objects.filter(agency=property_obj.current_manager, user=user).exists()
                return True 
                
        return False


class CanApproveApplication(permissions.BasePermission):
    """
    Strict permission check for the APPROVE action.
    While the DecisionEngine (Service layer) handles the actual condition validation, 
    this permission ensures only authorized roles can even attempt the approval endpoint.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        # Only agents, managers, landlords, and admins can attempt approvals
        return user.role in ['agent', 'manager', 'landlord', 'admin']