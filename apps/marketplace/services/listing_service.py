from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from django.db.models import Q, Min
from django.utils import timezone

class ListingService:
    """
    Handles the creation, retrieval, and lifecycle management of marketplace listings.
    Enforces strict visibility rules: only active properties with published status 
    and available units are exposed to the public.
    """

    @staticmethod
    @transaction.atomic
    def sync_listings_for_property(property):
        """
        ✅ AUTOMATIC BRIDGE: Generates marketplace Listing records 
        for a property and its unit groups whenever it is published.
        """
        Listing = apps.get_model('marketplace', 'Listing')
        
        # 1. Clear old listings for this property to prevent duplicates
        Listing.objects.filter(property=property).delete()
        
        # 2. Calculate the minimum rent amount for the landing page card
        min_rent = property.units.filter(status='available').aggregate(Min('rent_amount'))['rent_amount__min']
        if not min_rent:
            min_rent = property.unit_groups.aggregate(Min('base_rent_amount'))['base_rent_amount__min'] or 0
            
        # 3. Determine listing type (defaults to rental if not specified)
        listing_type = getattr(property, 'listing_type', 'rental') or 'rental'
        price_period = 'per month' if listing_type == 'rental' else 'per night' if listing_type == 'short_stay' else ''

        # 4. Create a master Property-Level Listing (Shows the whole property on the grid)
        Listing.objects.create(
            property=property,
            listing_type=listing_type,
            title=property.title,
            min_rent_amount=min_rent,
            price_period=price_period,
            status='active'
        )
        
        # 5. Create Unit-Group Level Listings (Allows filtering by specific unit types)
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

    @staticmethod
    @transaction.atomic
    def create_listing(property, unit=None, listing_type='rental', created_by=None):
        """
        Creates a new marketplace listing for a specific unit (if needed manually).
        """
        Listing = apps.get_model('marketplace', 'Listing')
        PropertyPublication = apps.get_model('marketplace', 'PropertyPublication')

        if not getattr(property, 'is_active', True):
            raise ValidationError("Cannot create a listing for an inactive property.")

        if unit:
            if unit.status != 'available':
                raise ValidationError(f"Unit {unit.unit_code} is not available for listing.")
            if unit.property_id != property.id:
                raise ValidationError("Unit does not belong to the specified property.")

        publication, created = PropertyPublication.objects.get_or_create(
            property=property,
            defaults={
                'is_published': False,
                'visibility_status': 'hidden',
                'published_by': created_by,
                'last_modified_by': created_by
            }
        )

        listing = Listing.objects.create(
            property=property,
            unit=unit,
            listing_type=listing_type,
            status='active',
            created_by=created_by
        )

        return listing

    @staticmethod
    def get_public_listings(filters=None):
        """
        Retrieves listings that are strictly visible to the public marketplace.
        Enforces NB Rule: property is active AND publication is visible AND unit is available.
        """
        Listing = apps.get_model('marketplace', 'Listing')
        
        # Base queryset for active, non-archived listings
        queryset = Listing.objects.filter(
            status='active'
        ).select_related('property', 'unit_group', 'property__location')

        # Enforce Publication Visibility Rules
        queryset = queryset.filter(
            property__is_active=True,
            property__publication__is_published=True,
            property__publication__visibility_status='visible'
        )

        # Enforce Unit Availability Rule: 
        # Allow property-level listings (unit_group__isnull=True) OR unit-specific listings that are 'available'
        queryset = queryset.filter(
            Q(unit_group__isnull=True) | Q(unit_group__capacity__gt=0)
        )

        # Apply dynamic filters (e.g., city, listing_type, price range)
        if filters:
            if filters.get('city'):
                queryset = queryset.filter(property__location__city__iexact=filters['city'])
            if filters.get('listing_type'):
                queryset = queryset.filter(listing_type=filters['listing_type'])

        return queryset.order_by('-created_at')

    @staticmethod
    @transaction.atomic
    def archive_listing(listing, user):
        """
        Archives a listing, removing it from public view permanently (e.g., property sold).
        """
        listing.status = 'archived'
        listing.save(update_fields=['status'])
        
        VisibilityLog = apps.get_model('marketplace', 'MarketplaceVisibilityLog')
        VisibilityLog.objects.create(
            property=listing.property,
            action='archived',
            performed_by=user,
            notes='Listing archived by user.'
        )