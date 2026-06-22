from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from ..models import PropertyPublication, MarketplaceVisibilityLog
from apps.properties.models import Property
from .listing_service import ListingService # ✅ ADDED IMPORT

class PublishingService:
    """
    Controls whether a property is publicly exposed on the marketplace.
    Enforces strict validation before allowing publication.
    """

    @staticmethod
    @transaction.atomic
    def publish_property(property: Property, user) -> PropertyPublication:
        """
        Publishes a property to the marketplace.
        Validates that it meets minimum requirements for public exposure.
        """
        if not property.is_active:
            raise ValidationError("Cannot publish an inactive property.")
            
        if not property.location:
            raise ValidationError("Property must have a location defined before publishing.")
            
        if not property.cover_photo and not property.media.exists():
            raise ValidationError("Property must have at least one cover photo or media item before publishing.")
            
        if not property.units.filter(status='available').exists():
            raise ValidationError("Property must have at least one available unit to be published.")

        publication, created = PropertyPublication.objects.get_or_create(property=property)
        publication.publish(user)
        
        # ✅🚨 CRITICAL BRIDGE: Auto-generate Listing records for the marketplace grid
        ListingService.sync_listings_for_property(property)
        
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=MarketplaceVisibilityLog.Action.PUBLISHED,
            performed_by=user,
            reason="Published to marketplace via dashboard"
        )
        
        return publication

    @staticmethod
    @transaction.atomic
    def hide_property(property: Property, user, reason: str = "") -> PropertyPublication:
        """
        Hides a property from the marketplace without unpublishing it.
        Internal operations (tenancy, payments) continue normally.
        """
        publication = PropertyPublication.objects.get(property=property)
        publication.hide(user)
        
        # ✅ Update Listing statuses to hidden so they drop off the public grid
        Listing = apps.get_model('marketplace', 'Listing')
        Listing.objects.filter(property=property).update(status='hidden')
        
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=MarketplaceVisibilityLog.Action.HIDDEN,
            performed_by=user,
            reason=reason or "Hidden by manager"
        )
        
        return publication

    @staticmethod
    @transaction.atomic
    def unpublish_property(property: Property, user, reason: str = "") -> PropertyPublication:
        """
        Completely unpublishes a property, removing it from all marketplace queries.
        """
        publication = PropertyPublication.objects.get(property=property)
        publication.unpublish(user)
        
        # ✅ Delete listings completely from the marketplace database
        Listing = apps.get_model('marketplace', 'Listing')
        Listing.objects.filter(property=property).delete()
        
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=MarketplaceVisibilityLog.Action.UNPUBLISHED,
            performed_by=user,
            reason=reason or "Unpublished by manager"
        )
        
        return publication