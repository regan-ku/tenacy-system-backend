from django.db import models
from django.conf import settings
# ✅ ADDED: Import ListingType
from .enums import PropertyCategory, PropertySubType, ConstructionType, OwnershipStatus, ListingType
from .location import Location

class Property(models.Model):
    """
    Defines a real-world property and its structural constraints.
    Acts as the parent entity for Unit Groups and Units.
    """
    title = models.CharField('Property Title', max_length=255, db_index=True)
    description = models.TextField('Description', blank=True, null=True)

    cover_photo = models.ImageField(
        'Cover Photo', 
        upload_to='properties/covers/', 
        blank=True, 
        null=True,
        help_text="Main display image for the property."
    )

    # Ownership & Management
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_properties',
        help_text="The landlord or agency user who created this property."
    )
    
    current_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_properties',
        help_text="The user or agency currently managing operations."
    )
    
    ownership_status = models.CharField(
        'Ownership Status',
        max_length=20,
        choices=OwnershipStatus.choices,
        default=OwnershipStatus.OWNED,
        db_index=True
    )

    # Structure & Categorization
    property_category = models.CharField('Category', max_length=20, choices=PropertyCategory.choices)
    property_sub_type = models.CharField('Sub-Type', max_length=30, choices=PropertySubType.choices)
    construction_type = models.CharField('Construction Type', max_length=20, choices=ConstructionType.choices, blank=True, null=True)
    
    # Capacity Rules
    number_of_floors = models.PositiveIntegerField('Number of Floors', default=1)
    total_units_capacity = models.PositiveIntegerField('Total Units Capacity', default=1, help_text="Maximum number of units this property can hold.")

    is_single_unit_property = models.BooleanField(
        'Is Single Unit Property', 
        default=False, 
        help_text="If True (e.g., Mansion, Bungalow, Plot), the unit group creation wizard is skipped."
    )

    # AMENITIES & FEATURES (Property Level Only)
    has_water = models.BooleanField('Has Water', default=True)
    has_electricity = models.BooleanField('Has Electricity', default=True)
    has_internet = models.BooleanField('Has Internet/Wi-Fi', default=False)
    has_cctv = models.BooleanField('Has CCTV Security', default=False)
    has_elevator = models.BooleanField('Has Elevator', default=False)
    has_generator = models.BooleanField('Has Backup Generator', default=False)
    has_gym = models.BooleanField('Has Gym', default=False)
    has_swimming_pool = models.BooleanField('Has Swimming Pool', default=False)
    allows_pets = models.BooleanField('Allows Pets', default=False)
    parking_spaces = models.PositiveIntegerField('Parking Spaces', default=0)

    # Relationships
    location = models.OneToOneField(
        Location,
        on_delete=models.CASCADE,
        related_name='property',
        help_text="Geographic and address details."
    )

    # ✅ NEW: Marketplace Visibility & Listing Type (For Wizard Step 6)
    is_published = models.BooleanField(
        'Published to Marketplace', 
        default=False,
        help_text="If true, this property is visible on the public marketplace."
    )
    
    listing_type = models.CharField(
        'Listing Type', 
        max_length=20, 
        choices=ListingType.choices,
        blank=True, 
        null=True,
        help_text="Determines how the property is categorized on the marketplace (Rental, Sale, Short Stay)."
    )

    # Timestamps & Status
    is_active = models.BooleanField('Is Active (Wizard Complete)', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property_category', 'property_sub_type']),
            models.Index(fields=['is_active', 'ownership_status']),
            models.Index(fields=['is_published', 'listing_type']), # ✅ Optimized for marketplace queries
        ]

    def __str__(self):
        return f"{self.title} ({self.get_property_sub_type_display()})"

    @property
    def current_occupied_units(self):
        return self.units.filter(status='occupied').count()

    @property
    def is_marketplace_ready(self):
        # ✅ UPDATED: A property is only ready for the marketplace if it is active, published, and has units/media
        return self.is_active and self.is_published and self.location and self.units.exists()