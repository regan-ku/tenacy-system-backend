from rest_framework import permissions
from ..models.roles import UserRole  # Ensure this path matches your project structure


def IsRole(*allowed_roles):
    """
    Custom permission factory to only allow users of specific roles to access the view.
    
    Usage: 
        permission_classes = [IsRole(UserRole.LANDLORD, UserRole.AGENCY)]
    """
    class _IsRole(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Check if the user's role is in the allowed roles passed to the factory
            return request.user.role in allowed_roles
            
    return _IsRole


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` or `user` attribute.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request (e.g., GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object or Admin
        if request.user.role == UserRole.ADMIN:
            return True
            
        # Safely check for 'user' or 'owner' attributes
        return (hasattr(obj, 'user') and obj.user == request.user) or \
               (hasattr(obj, 'owner') and obj.owner == request.user)


class IsVerifiedUser(permissions.BasePermission):
    """
    Ensures the user has passed identity/business verification.
    Critical for Landlords and Agencies before they can manage properties.
    """
    def has_permission(self, request, view):
        # Using getattr prevents AttributeError if the field is somehow missing
        return request.user.is_authenticated and getattr(request.user, 'is_verified', False)