from django.db import models
from django.conf import settings

class TenancyExtension(models.Model):
    """
    Manages requests and approvals for extending a tenancy beyond its original end date.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    tenancy = models.ForeignKey(
        'Tenancy',
        on_delete=models.CASCADE,
        related_name='extensions',
        help_text="The tenancy being extended."
    )

    requested_new_end_date = models.DateField(
        'Requested New End Date',
        help_text="The date the tenant wishes to extend the tenancy to."
    )

    proposed_rent_adjustment = models.DecimalField(
        'Proposed Rent Adjustment',
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Any proposed increase or decrease in rent for the extension period."
    )

    reason = models.TextField('Reason for Extension', blank=True, null=True)

    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_extensions'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_extensions'
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Tenancy Extension'
        verbose_name_plural = 'Tenancy Extensions'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['tenancy', 'status']),
        ]

    def __str__(self):
        return f"Extension request for {self.tenancy.unit.unit_code} to {self.requested_new_end_date}"