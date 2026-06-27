from django.db import models
from django.conf import settings

class TenancyTermination(models.Model):
    """
    Records the formal end of a tenancy. 
    Triggers the release of unit occupancy and finalizes the tenancy history.
    """
    class TerminationType(models.TextChoices):
        TENANT_REQUEST = 'tenant_request', 'Tenant Request'
        LANDLORD_REQUEST = 'landlord_request', 'Landlord Request'
        BREACH_OF_CONTRACT = 'breach', 'Breach of Contract'
        EXPIRY = 'expiry', 'Natural Expiry'
        MUTUAL_AGREEMENT = 'mutual', 'Mutual Agreement'

    tenancy = models.OneToOneField(
        'Tenancy',
        on_delete=models.PROTECT,
        related_name='termination_record',
        help_text="The tenancy being terminated."
    )

    termination_type = models.CharField(
        'Termination Type',
        max_length=20,
        choices=TerminationType.choices
    )

    notes = models.TextField(
        'Termination Notes', 
        blank=True, 
        null=True,
        help_text="Detailed explanation or handover notes."
    )

    penalty_applied = models.DecimalField(
        'Penalty Applied', 
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Any early termination fees or damage deductions."
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_terminations',
        help_text="Manager, landlord, or admin who approved the termination."
    )

    # ✅ KEPT AS effective_date for legal/DB clarity
    effective_date = models.DateField(
        'Effective Termination Date',
        help_text="The date the unit is officially vacated and released."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tenancy Termination'
        verbose_name_plural = 'Tenancy Terminations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenancy', 'termination_type']),
        ]

    def __str__(self):
        return f"Termination of {self.tenancy.unit.unit_code} ({self.get_termination_type_display()})"

    # ✅ NEW: Property alias for frontend/API consistency
    @property
    def move_out_date(self):
        """
        Alias for effective_date.
        Used by serializers/frontend for user-friendly naming.
        'Move out date' and 'effective date' are the same thing in this context.
        """
        return self.effective_date

    @move_out_date.setter
    def move_out_date(self, value):
        """Allows setting via the alias."""
        self.effective_date = value