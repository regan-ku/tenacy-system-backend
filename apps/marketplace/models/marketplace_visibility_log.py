from django.db import models
from django.conf import settings
from django.utils import timezone

class MarketplaceVisibilityLog(models.Model):
    """
    Immutable audit trail for all property publication and visibility changes.
    Critical for compliance, dispute resolution, and tracking marketplace exposure.
    """
    class Action(models.TextChoices):
        PUBLISHED = 'published', 'Published to Marketplace'
        HIDDEN = 'hidden', 'Hidden from Marketplace'
        UNPUBLISHED = 'unpublished', 'Unpublished'
        RESTORED = 'restored', 'Restored to Visibility'
        SUSPENDED = 'suspended', 'Suspended by Admin'

    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='visibility_logs',
        help_text="The property whose visibility changed."
    )
    
    publication = models.ForeignKey(
        'PropertyPublication',
        on_delete=models.CASCADE,
        related_name='visibility_logs',
        help_text="The publication record that was modified."
    )
    
    action = models.CharField(
        'Action Taken',
        max_length=20,
        choices=Action.choices
    )
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='visibility_changes_performed',
        help_text="The user (landlord, agency, or admin) who made the change."
    )
    
    reason = models.TextField('Reason for Change', blank=True, null=True, help_text="Optional note explaining the action.")
    timestamp = models.DateTimeField('Timestamp', auto_now_add=True)

    class Meta:
        verbose_name = 'Marketplace Visibility Log'
        verbose_name_plural = 'Marketplace Visibility Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['property', 'timestamp']),
            models.Index(fields=['performed_by', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.get_action_display()} on {self.property.title}"