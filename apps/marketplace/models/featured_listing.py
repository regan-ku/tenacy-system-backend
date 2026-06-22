from django.db import models
from django.utils import timezone

class FeaturedListing(models.Model):
    """
    Controls homepage promotions, premium exposure, and featured sections.
    Allows landlords/agencies to boost visibility for specific listings.
    """
    class Placement(models.TextChoices):
        HOMEPAGE_HERO = 'homepage_hero', 'Homepage Hero Banner'
        FEATURED_SECTION = 'featured_section', 'Featured Listings Grid'
        CATEGORY_TOP = 'category_top', 'Category Top (e.g., Top in Nairobi)'

    listing = models.ForeignKey(
        'Listing',
        on_delete=models.CASCADE,
        related_name='featured_placements',
        help_text="The marketplace listing being featured."
    )

    placement = models.CharField(
        'Placement',
        max_length=30,
        choices=Placement.choices,
        default=Placement.FEATURED_SECTION
    )

    is_active = models.BooleanField('Is Active', default=True)
    
    start_date = models.DateTimeField('Start Date', default=timezone.now)
    end_date = models.DateTimeField('End Date', blank=True, null=True, help_text="Leave blank for indefinite featured status.")
    
    priority = models.PositiveIntegerField(
        'Priority', 
        default=0, 
        help_text="Higher number = higher display priority within the same placement."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Featured Listing'
        verbose_name_plural = 'Featured Listings'
        ordering = ['-priority', '-start_date']
        indexes = [
            models.Index(fields=['is_active', 'placement', 'start_date']),
        ]

    def __str__(self):
        return f"Featured: {self.listing.title} ({self.get_placement_display()})"

    def is_currently_active(self):
        """Helper to check if the feature is currently within its time window."""
        now = timezone.now()
        if self.end_date:
            return self.is_active and self.start_date <= now <= self.end_date
        return self.is_active and self.start_date <= now