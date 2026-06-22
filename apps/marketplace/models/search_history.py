from django.db import models
from django.conf import settings

class SearchHistory(models.Model):
    """
    Tracks user search queries and applied filters.
    Used for:
    1. "Recent Searches" UI feature
    2. Personalized property recommendations
    3. Marketplace demand analytics (e.g., "Most searched estates")
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_history',
        help_text="Authenticated user. Null for anonymous public visitors."
    )
    
    session_id = models.CharField(
        'Session ID', 
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Tracks anonymous user searches via session cookie."
    )
    
    search_query = models.CharField(
        'Search Query', 
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Raw text entered in search bar (e.g., '2 bedroom kilimani')"
    )
    
    # Stores applied filters as JSON for recommendation engine
    # Example: {"city": "Nairobi", "min_price": 15000, "unit_type": "two_bedroom"}
    filters_applied = models.JSONField(
        'Filters Applied', 
        default=dict, 
        blank=True, 
        null=True
    )
    
    results_count = models.PositiveIntegerField(
        'Results Count', 
        default=0, 
        help_text="Number of properties returned by this search."
    )
    
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Search History'
        verbose_name_plural = 'Search History Records'
        ordering = ['-searched_at']
        indexes = [
            models.Index(fields=['user', 'searched_at']),
            models.Index(fields=['session_id', 'searched_at']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else f"Anonymous ({self.session_id})"
        return f"Search by {user_str}: '{self.search_query or 'Filtered Search'}' ({self.searched_at.strftime('%Y-%m-%d')})"