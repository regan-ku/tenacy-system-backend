from django.db import models
from django.conf import settings

class TenancyWaiver(models.Model):
    """
    Records formal approvals for waiving deposits or service charges.
    Ensures financial exceptions are properly authorized and audited.
    """
    class WaiverType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit Waiver'
        SERVICE_CHARGE = 'service_charge', 'Service Charge Waiver'
        BOTH = 'both', 'Both Deposit and Service Charge'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    tenancy = models.ForeignKey(
        'Tenancy',
        on_delete=models.CASCADE,
        related_name='waivers',
        help_text="The tenancy requesting the waiver."
    )

    waiver_type = models.CharField(
        'Waiver Type',
        max_length=20,
        choices=WaiverType.choices
    )

    reason = models.TextField(
        'Reason for Waiver',
        help_text="Justification for waiving the fee (e.g., promotional offer, tenant hardship)."
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_waivers'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_waivers',
        help_text="Manager, landlord, or admin who approved the waiver."
    )

    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Tenancy Waiver'
        verbose_name_plural = 'Tenancy Waivers'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['tenancy', 'status']),
        ]

    def __str__(self):
        return f"Waiver ({self.get_waiver_type_display()}) for {self.tenancy.unit.unit_code}"