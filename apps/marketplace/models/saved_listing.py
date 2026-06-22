from django.db import models
from django.conf import settings

class SavedListing(models.Model):
    """
    Allows authenticated users to bookmark or save listings for later viewing.
    Drives personalized recommendations and retargeting workflows.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_listings',
        help_text="The user who saved this listing."
    )
    
    listing = models.ForeignKey(
        'Listing',
        on_delete=models.CASCADE,
        related_name='saved_by_users',
        help_text="The marketplace listing being saved."
    )
    
    notes = models.TextField('User Notes', blank=True, null=True, help_text="Optional personal note (e.g., 'Good for family')")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Saved Listing'
        verbose_name_plural = 'Saved Listings'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'listing'],
                name='unique_saved_listing_per_user'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} saved {self.listing.title}"