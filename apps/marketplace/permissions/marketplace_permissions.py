from rest_framework import permissions

class IsMarketplaceReadOnly(permissions.BasePermission):
    """
    Allows public read-only access to marketplace listings.
    Write operations (POST, PUT, PATCH, DELETE) are denied for public users.
    """
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests to anyone (public browsing)
        if request.method in permissions.SAFE_METHODS:
            return True
        # Require authentication for any modifications
        return request.user and request.user.is_authenticated


class CanManagePropertyPublication(permissions.BasePermission):
    """
    Allows only the property owner (created_by) or the current delegated manager 
    to publish, hide, or unpublish a property on the marketplace.
    """
    def has_object_permission(self, request, view, obj):
        # obj can be a Property or a PropertyPublication
        property_obj = getattr(obj, 'property', obj)
        
        return (
            property_obj.created_by == request.user or
            property_obj.current_manager == request.user or
            request.user.role == 'admin'
        )


class CanSaveListings(permissions.BasePermission):
    """
    Ensures that only authenticated users can save/bookmark listings.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated