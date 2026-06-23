from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from apps.properties.models.property import Property

@receiver(pre_save, sender=Property)
def capture_property_publication_state(sender, instance, **kwargs):
    """
    Captures the previous state of is_published and is_active before saving.
    This allows the post_save signal to detect if a change actually occurred.
    """
    if instance.pk:
        try:
            previous = Property.objects.get(pk=instance.pk)
            instance._previous_is_published = previous.is_published
            instance._previous_is_active = previous.is_active
        except Property.DoesNotExist:
            instance._previous_is_published = False
            instance._previous_is_active = False
    else:
        # New property being created
        instance._previous_is_published = False
        instance._previous_is_active = False

@receiver(post_save, sender=Property)
def sync_property_marketplace_status(sender, instance, **kwargs):
    """
    Automatically syncs the property's marketplace status whenever it is saved.
    This ensures that changes made via the Django Admin panel, frontend API, 
    or programmatically all trigger the exact same marketplace publishing logic.
    """
    # Import locally to prevent circular import issues between properties and marketplace apps
    from apps.marketplace.services.publishing_service import PublishingService
    
    # Check if the publication status actually changed
    prev_published = getattr(instance, '_previous_is_published', False)
    prev_active = getattr(instance, '_previous_is_active', False)
    
    # If nothing changed regarding publication, skip the heavy marketplace sync
    if instance.is_published == prev_published and instance.is_active == prev_active:
        return

    is_published = getattr(instance, 'is_published', False)
    is_active = getattr(instance, 'is_active', True)
    
    # Determine the user to attribute this action to.
    # For admin/programmatic saves, we fallback to the property's owner/manager.
    user = instance.current_manager or instance.created_by
    
    if not user:
        print(f"[Marketplace Sync Signal] Skipping sync for '{instance.title}' because no user could be determined.")
        return

    try:
        if is_published and is_active:
            PublishingService.publish_property(instance, user)
            print(f"✅ [Signal] Property '{instance.title}' successfully published to marketplace.")
        else:
            PublishingService.unpublish_property(instance)
            print(f"✅ [Signal] Property '{instance.title}' successfully unpublished from marketplace.")
    except Exception as e:
        # Log the error but don't crash the save operation
        print(f"[Marketplace Sync Signal Error] Failed to sync '{instance.title}': {e}")