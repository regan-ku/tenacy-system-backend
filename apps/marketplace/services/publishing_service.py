from django.db import transaction
from django.db.models import Min
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import PropertyPublication, Listing, MarketplaceVisibilityLog

class PublishingService:
    """
    Handles the actual publishing, hiding, and unpublishing of properties to the marketplace.
    Creates the necessary Publication and Listing records, and logs all actions.
    """

    @staticmethod
    @transaction.atomic
    def publish_property(property, user):
        """
        Publishes a property to the marketplace.
        """
        if not property.is_active:
            raise ValidationError("Cannot publish an inactive property.")

        # 1. Create or update the PropertyPublication record
        publication, created = PropertyPublication.objects.get_or_create(
            property=property,
            defaults={
                'is_published': True,
                'visibility_status': 'visible',
                'published_by': user,
                'last_modified_by': user
            }
        )
        
        if not created:
            publication.is_published = True
            publication.visibility_status = 'visible'
            publication.published_at = timezone.now()
            publication.unpublished_at = None
            publication.last_modified_by = user
            publication.save(update_fields=[
                'is_published', 'visibility_status', 'published_at', 
                'unpublished_at', 'last_modified_by', 'updated_at'
            ])

        # 2. Generate Marketplace Listings
        PublishingService._generate_listings(property)

        # 3. Audit Log
        # ✅ FIX 1: Changed 'notes' to 'reason'
        # ✅ FIX 2: Added the required 'publication' object
        MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action='published',
            performed_by=user,
            reason='Property published to marketplace.'
        )
            
        print(f"✅ Property '{property.title}' successfully published to marketplace.")

    @staticmethod
    @transaction.atomic
    def hide_property(property, user):
        """
        Temporarily hides a property from the marketplace without deleting listings.
        """
        # Fetch publication before updating to use in the audit log
        publication = PropertyPublication.objects.filter(property=property).first()

        PropertyPublication.objects.filter(property=property).update(
            is_published=False,
            visibility_status='hidden',
            last_modified_by=user,
            unpublished_at=timezone.now()
        )
        
        # Hide listings but keep them in database for quick restoration
        Listing.objects.filter(property=property).update(status='hidden')

        # Audit Log
        if publication:
            MarketplaceVisibilityLog.objects.create(
                property=property,
                publication=publication,
                action='hidden',
                performed_by=user,
                reason='Property temporarily hidden from marketplace.'
            )

        print(f"✅ Property '{property.title}' successfully hidden from marketplace.")

    @staticmethod
    @transaction.atomic
    def unpublish_property(property, user=None):
        """
        Completely removes a property from the marketplace and deletes all listings.
        """
        # Fetch publication before updating to use in the audit log
        publication = PropertyPublication.objects.filter(property=property).first()

        PropertyPublication.objects.filter(property=property).update(
            is_published=False,
            visibility_status='unpublished',
            last_modified_by=user,
            unpublished_at=timezone.now()
        )
        
        # Delete all listings entirely
        Listing.objects.filter(property=property).delete()

        # Audit Log
        if publication and user:
            MarketplaceVisibilityLog.objects.create(
                property=property,
                publication=publication,
                action='unpublished',
                performed_by=user,
                reason='Property permanently unpublished from marketplace.'
            )

        print(f"✅ Property '{property.title}' successfully unpublished from marketplace.")

    @staticmethod
    def _generate_listings(property):
        """
        Internal helper to generate marketplace listings for a property.
        Clears old listings first to prevent duplicates.
        """
        # Clear old listings to prevent duplicates
        Listing.objects.filter(property=property).delete()
        
        # Calculate minimum rent for the main property card
        min_rent = property.units.filter(status='available').aggregate(Min('rent_amount'))['rent_amount__min'] or 0
        listing_type = getattr(property, 'listing_type', 'rental') or 'rental'

        # Create the main Property-Level Listing
        Listing.objects.create(
            property=property,
            listing_type=listing_type,
            title=property.title,
            min_rent_amount=min_rent,
            price_period='per month' if listing_type == 'rental' else 'per night' if listing_type == 'short_stay' else '',
            status='active'
        )
        
        # Create Unit-Group Level Listings
        for group in property.unit_groups.all():
            Listing.objects.create(
                property=property,
                unit_group=group,
                listing_type=listing_type,
                title=f"{property.title} - {group.name}",
                min_rent_amount=group.base_rent_amount,
                price_period=f'per {group.billing_cycle}',
                status='active'
            )