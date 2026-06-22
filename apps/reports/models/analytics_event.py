from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AnalyticsEvent(models.Model):
    """
    Tracks user interactions and system events for advanced analytics.
    Feeds the 'System Intelligence' layer for behavioral analysis and conversion tracking.
    """
    class EventType(models.TextChoices):
        MARKETPLACE_VIEW = 'marketplace_view', 'Marketplace Listing Viewed'
        APPLICATION_STARTED = 'application_started', 'Rental Application Started'
        APPLICATION_SUBMITTED = 'application_submitted', 'Rental Application Submitted'
        PAYMENT_INITIATED = 'payment_initiated', 'Payment Initiated'
        PAYMENT_SUCCESS = 'payment_success', 'Payment Successful'
        MAINTENANCE_REQUESTED = 'maintenance_requested', 'Maintenance Requested'
        DASHBOARD_ACCESSED = 'dashboard_accessed', 'Dashboard Accessed'

    event_type = models.CharField(
        'Event Type',
        max_length=50,
        choices=EventType.choices,
        db_index=True
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_events',
        help_text="User who triggered the event (null for anonymous marketplace views)."
    )

    # Generic relation to the entity involved (e.g., a specific Property, Unit, or Tenancy)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Additional context (e.g., search query, device type, referral source)
    metadata = models.JSONField(
        'Event Metadata',
        default=dict,
        blank=True,
        help_text="Additional context like search filters, device info, or conversion value."
    )

    timestamp = models.DateTimeField('Event Timestamp', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Analytics Event'
        verbose_name_plural = 'Analytics Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['user', 'event_type']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"[{self.get_event_type_display()}] by {user_str} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"