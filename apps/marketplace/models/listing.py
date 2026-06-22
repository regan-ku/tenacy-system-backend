from django.db import models

class Listing(models.Model):
    """
    Public-facing marketplace record optimized for fast landing page rendering.
    Displays: Cover Photo, Name, Location, Min Rent, and "View" button.
    """
    class ListingType(models.TextChoices):
        RENTAL = 'rental', 'Rental'
        SALE = 'sale', 'For Sale'
        SHORT_STAY = 'short_stay', 'Short Stay'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        UNAVAILABLE = 'unavailable', 'Unavailable (Fully Occupied)'
        HIDDEN = 'hidden', 'Hidden'
        ARCHIVED = 'archived', 'Archived'

    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='marketplace_listings'
    )

    unit_group = models.ForeignKey(
        'properties.UnitGroup',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='marketplace_listings',
        help_text="Specific unit group (for rental listings). Null if whole property."
    )

    listing_type = models.CharField('Listing Type', max_length=20, choices=ListingType.choices)
    
    # CACHED FIELDS FOR BLAZING FAST LANDING PAGE GRID
    cover_photo = models.ImageField(
        'Landing Page Cover Photo', 
        upload_to='marketplace/covers/', 
        blank=True, 
        null=True,
        help_text="Main image shown on the marketplace landing page."
    )
    
    title = models.CharField('Listing Title', max_length=255)
    location_summary = models.CharField(
        'Location Summary', 
        max_length=255, 
        help_text="e.g., 'Kilimani, Nairobi' (Cached for fast grid rendering)"
    )
    
    min_rent_amount = models.DecimalField(
        'Min Rent Amount', 
        max_digits=12, 
        decimal_places=2, 
        help_text="Starting price shown on landing page card."
    )
    
    price_period = models.CharField(
        'Price Period', 
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="e.g., 'per month', 'per night'"
    )

    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Marketplace Listing'
        verbose_name_plural = 'Marketplace Listings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'listing_type']),
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_listing_type_display()})"

    def save(self, *args, **kwargs):
        # Auto-sync cover photo and location from property if not explicitly set
        if not self.cover_photo and self.property.cover_photo:
            self.cover_photo = self.property.cover_photo
            
        if not self.location_summary and self.property.location:
            loc = self.property.location
            self.location_summary = f"{loc.estate or ''}, {loc.city}".strip(', ')
            
        super().save(*args, **kwargs)


        