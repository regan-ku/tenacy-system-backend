from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import PropertyPublication, Listing, MarketplaceVisibilityLog

class VisibilityService:
    """
    Controls listing exposure, hidden states, and suspension logic.
    Allows managers to temporarily hide properties without unpublishing them.
    """

    @staticmethod
    @transaction.atomic
    def hide_property(property, user, reason: str = ""):
        """
        Hides a property from the marketplace. Internal operations continue normally.
        """
        publication = PropertyPublication.objects.get(property=property)
        publication.visibility_status = PropertyPublication.VisibilityStatus.HIDDEN
        publication.last_modified_by = user
        publication.save(update_fields=['visibility_status', 'last_modified_by'])
        
        # Hide all associated listings
        Listing.objects.filter(property=property, status='active').update(status='hidden')
        
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=MarketplaceVisibilityLog.Action.HIDDEN,
            performed_by=user,
            reason=reason or "Temporarily hidden by manager"
        )

    @staticmethod
    @transaction.atomic
    def restore_property(property, user, reason: str = ""):
        """
        Restores a hidden property to visible status in the marketplace.
        """
        publication = PropertyPublication.objects.get(property=property)
        
        if not publication.is_published:
            raise ValidationError("Cannot restore an unpublished property. It must be published first.")
            
        publication.visibility_status = PropertyPublication.VisibilityStatus.VISIBLE
        publication.last_modified_by = user
        publication.save(update_fields=['visibility_status', 'last_modified_by'])
        
        # Restore associated listings if they have available units
        Listing.objects.filter(property=property, status='hidden').update(status='active')
        
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=MarketplaceVisibilityLog.Action.RESTORED,
            performed_by=user,
            reason=reason or "Restored to marketplace visibility"
        )

    @staticmethod
    @transaction.atomic
    def suspend_property(property, user, reason: str = ""):
        """
        Admin-level action to suspend a property (e.g., due to fraud or policy violations).
        """
        if user.role != 'admin':
            raise ValidationError("Only system administrators can suspend properties.")
            
        publication = PropertyPublication.objects.get(property=property)
        publication.visibility_status = PropertyPublication.VisibilityStatus.SUSPENDED
        publication.last_modified_by = user
        publication.save(update_fields=['visibility_status', 'last_modified_by'])
        
        Listing.objects.filter(property=property).update(status='hidden')
        
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=MarketplaceVisibilityLog.Action.SUSPENDED,
            performed_by=user,
            reason=reason or "Suspended by system administrator"
        )