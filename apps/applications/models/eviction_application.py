from django.db import models

class EvictionApplication(models.Model):
    """
    Extends the base Application model for tenant-initiated eviction/termination notices.
    Treats a tenant's request to leave as a formal application requiring manager approval.
    """
    application = models.OneToOneField(
        'Application',
        on_delete=models.CASCADE,
        related_name='eviction_details',
        help_text="The base application record this eviction notice extends."
        # Note: For eviction, the 'unit' FK on the base Application model 
        # represents the unit the tenant is currently occupying and wants to leave.
    )

    notice_period_days = models.PositiveIntegerField(
        'Notice Period (Days)',
        help_text="Number of days of notice being given (e.g., 30, 60)."
    )

    intended_vacate_date = models.DateField(
        'Intended Vacate Date',
        help_text="The exact date the tenant plans to hand over the unit."
    )

    reason_for_leaving = models.TextField(
        'Reason for Leaving',
        blank=True,
        null=True,
        help_text="Optional explanation for the early termination or notice."
    )

    forwarding_address = models.TextField(
        'Forwarding Address',
        blank=True,
        null=True,
        help_text="Where the tenant can be reached for deposit refund or final correspondence."
    )

    class Meta:
        verbose_name = 'Eviction Notice Application'
        verbose_name_plural = 'Eviction Notice Applications'

    def __str__(self):
        return f"Eviction Notice for {self.application.unit.unit_code} (Vacating: {self.intended_vacate_date})"