from django.db import models
from django.conf import settings

class Application(models.Model):
    """
    Base model for all application types (Rental, Transfer, Eviction Notice).
    Tracks the applicant, target property/unit, and core workflow status.
    """
    class ApplicationType(models.TextChoices):
        RENTAL = 'rental', 'Rental Application'
        TRANSFER = 'transfer', 'Transfer Application'
        EVICTION_NOTICE = 'eviction_notice', 'Eviction Notice (Tenant Initiated)'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        UNDER_REVIEW = 'under_review', 'Under Review'
        ESCALATED = 'escalated', 'Escalated to Manager'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
        EXPIRED = 'expired', 'Expired'

    # Auto-populated from Accounts App
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='applications',
        help_text="The user submitting the application."
    )

    # Auto-populated from Properties App
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='applications',
        help_text="The target property for this application."
    )

    unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='applications',
        help_text="The specific target unit (nullable for property-wide eviction notices)."
    )

    application_type = models.CharField(
        'Application Type',
        max_length=20,
        choices=ApplicationType.choices,
        default=ApplicationType.RENTAL
    )

    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['applicant', 'status']),
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        target = self.unit.unit_code if self.unit else self.property.title
        return f"{self.get_application_type_display()} for {target} by {self.applicant.email}"