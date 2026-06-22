from rest_framework import permissions
from ..models import MaintenanceRequest

class IsTenantOrOwnerOfRequest(permissions.BasePermission):
    """
    Ensures users only access maintenance data they are authorized to see.
    - Tenants: Can view requests for units they occupy.
    - Landlords/Agents: Can view requests for properties they own/manage.
    - Staff: Full access.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff:
            return True
            
        # 1. Creator Check (Tenant who reported it)
        if obj.created_by == user:
            return True
            
        # 2. Property Owner/Manager Check
        # Assuming Property model has 'owner' and 'manager' fields
        prop = obj.property
        if hasattr(prop, 'owner') and prop.owner == user:
            return True
        if hasattr(prop, 'manager') and prop.manager == user:
            return True
            
        # 3. Assigned Technician Check (If they need to see details to fix it)
        if obj.assigned_to == user:
            return True
            
        return False

class IsMaintenanceStaffOrAdmin(permissions.BasePermission):
    """
    Restricts administrative actions (creation of categories, bulk assignments, SLA overrides)
    to verified staff, agents, or administrators.
    """
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.is_staff or 
            getattr(user, 'role', None) in ['landlord', 'agent', 'manager', 'admin']
        )

class IsAssignedTechnicianOrAdmin(permissions.BasePermission):
    """
    Restricts status updates (e.g., marking 'In Progress', 'Resolved') 
    to the specific caretaker/technician assigned to the task.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff:
            return True
            
        # Check if the user is the one assigned to the work
        if obj.assigned_to == user:
            return True
            
        # Allow property owner to intervene manually
        prop = obj.property
        if hasattr(prop, 'owner') and prop.owner == user:
            return True
            
        return False