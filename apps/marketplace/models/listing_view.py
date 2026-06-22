from django.db import models
from django.conf import settings

class ListingView(models.Model):
    """
    Tracks listing impressions and views for analytics and trending algorithms.
    Supports both authenticated users and anonymous public visitors.
    """
    class ViewSource(models.TextChoices):
        SEARCH = 'search', 'Search Results'
        FEATURED = 'featured', 'Featured Section'
        NEARBY = 'nearby', 'Nearby / Geo Search'
        DIRECT = 'direct', 'Direct Link / Property Detail'
        RECOMMENDATION = 'recommendation', 'AI Recommendation'

    listing = models.ForeignKey(
        'Listing',
        on_delete=models.CASCADE,
        related_name='views',
        help_text="The listing that was viewed."
    )
    
    # Nullable for anonymous public visitors
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='listing_views',
        help_text="Authenticated user who viewed (null for public visitors)."
    )
    
    source = models.CharField(
        'View Source',
        max_length=20,
        choices=ViewSource.choices,
        default=ViewSource.DIRECT,
        help_text="How the user arrived at this listing."
    )
    
    ip_address = models.GenericIPAddressField('IP Address', blank=True, null=True, help_text="For duplicate view throttling.")
    user_agent = models.CharField('User Agent', max_length=500, blank=True, null=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Listing View'
        verbose_name_plural = 'Listing Views'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['listing', 'viewed_at']),
            models.Index(fields=['source', 'viewed_at']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"View: {self.listing.title} by {user_str} ({self.viewed_at.strftime('%Y-%m-%d')})"