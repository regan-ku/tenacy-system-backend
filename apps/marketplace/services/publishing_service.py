from django.db import transaction
from django.db.models import Min
from django.core.exceptions import ValidationError
from ..models import PropertyPublication, Listing

class PublishingService:
    """
    Handles the actual publishing and unpublishing of properties to the marketplace.
    Creates the necessary Publication and Listing records.
    """

    @staticmethod
    @transaction.atomic
    def publish_property(property, user):
        """
        Publishes a property to the marketplace.
        1. Creates/Updates the PropertyPublication record.
        2. Generates Listing records for the property and its unit groups.
        """
        if not property.is_active:
            raise ValidationError("Cannot publish an inactive property.")

        # 1. Create or update the PropertyPublication record
        publication, created = PropertyPublication.objects.get_or_create(
            property=property,
            defaults={
                'is_published': True,
                'visibility_status': 'visible',
                'published_by': user
            }
        )
        
        if not created:
            publication.is_published = True
            publication.visibility_status = 'visible'
            publication.last_modified_by = user
            publication.save(update_fields=['is_published', 'visibility_status', 'last_modified_by'])

        # 2. Generate Marketplace Listings
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
            price_period='per month' if listing_type == 'rental' else '',
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
            
        print(f"✅ Property '{property.title}' successfully published to marketplace.")

    @staticmethod
    @transaction.atomic
    def unpublish_property(property):
        """
        Unpublishes a property, hiding it from the public marketplace.
        """
        PropertyPublication.objects.filter(property=property).update(
            is_published=False, 
            visibility_status='hidden'
        )
        
        # Hide all associated listings
        Listing.objects.filter(property=property).update(status='hidden')
        print(f"✅ Property '{property.title}' successfully unpublished from marketplace.")