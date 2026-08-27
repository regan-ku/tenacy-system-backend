# apps/marketplace/signals.py
"""
Marketplace sync signals.

The marketplace app is a CONSUMER of the properties app.
These signals keep listing snapshots (price, availability, title, photos)
fresh whenever a landlord edits anything, from admin OR the API.
"""
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.properties.models import Property, Unit, UnitGroup


def _refresh_property_marketplace(property_obj):
    """
    Central refresh routine: re-syncs every unit-group listing + the master
    property listing, then clears the cache.
    """
    from .services.listing_service import ListingService
    from .services.unit_group_listing_service import UnitGroupListingService

    # Sync ALL groups of the property (covers unit moved between groups, etc.)
    for group in property_obj.unit_groups.all():
        UnitGroupListingService.sync_unit_group_to_marketplace(group)

    # Refresh the master "Starting from" card
    ListingService.update_listing_aggregates(property_obj)

    cache.clear()


@receiver([post_save, post_delete], sender=Unit)
def sync_marketplace_on_unit_change(sender, instance, **kwargs):
    """
    🔔 Fires on ANY unit save/delete: rent edits, status changes, unit moves.
    Works for Django Admin edits AND API edits (PATCH /api/units/{id}/).
    """
    _refresh_property_marketplace(instance.property)


@receiver(post_save, sender=UnitGroup)
def sync_marketplace_on_group_change(sender, instance, **kwargs):
    """
    🔔 Fires when a landlord edits a group's base rent, billing cycle, capacity.
    """
    _refresh_property_marketplace(instance.property)


@receiver(post_delete, sender=UnitGroup)
def cleanup_marketplace_on_group_delete(sender, instance, **kwargs):
    """
    🔔 If a unit group is deleted, remove its marketplace listing too.
    """
    from .models import Listing
    from .services.listing_service import ListingService

    Listing.objects.filter(unit_group_id=instance.id).delete()
    ListingService.update_listing_aggregates(instance.property)
    cache.clear()


@receiver(post_save, sender=Property)
def sync_marketplace_on_property_change(sender, instance, **kwargs):
    """
    🔔 Fires when the landlord edits property-level info (title, cover photo,
    location, description) so the copied listing fields stay fresh.
    """
    # Only refresh if the property is actually published to the marketplace
    if hasattr(instance, 'publication') and instance.publication.is_published:
        _refresh_property_marketplace(instance)