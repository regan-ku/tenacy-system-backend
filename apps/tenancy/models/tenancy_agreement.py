from django.db import models

class TenancyAgreement(models.Model):
    """
    Manages the digital lease contracts, terms, and signature tracking 
    associated with a specific tenancy record.
    """
    class AgreementType(models.TextChoices):
        RENTAL = 'rental', 'Standard Rental Agreement'
        LEASE = 'lease', 'Fixed-Term Lease'
        SHORT_STAY = 'short_stay', 'Short Stay Agreement'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_SIGNATURE = 'pending_signature', 'Pending Signature'
        SIGNED = 'signed', 'Signed & Active'
        EXPIRED = 'expired', 'Expired'
        TERMINATED = 'terminated', 'Terminated'

    tenancy = models.OneToOneField(
        'Tenancy',
        on_delete=models.CASCADE,
        related_name='agreement',
        help_text="The tenancy this agreement belongs to."
    )

    agreement_type = models.CharField(
        'Agreement Type',
        max_length=20,
        choices=AgreementType.choices,
        default=AgreementType.RENTAL
    )

    start_date = models.DateField('Agreement Start Date')
    end_date = models.DateField('Agreement End Date', blank=True, null=True)
    
    terms_and_conditions = models.TextField(
        'Terms and Conditions', 
        blank=True, 
        null=True,
        help_text="Specific rules, house rules, or custom clauses for this tenancy."
    )
    
    digital_signature_url = models.URLField(
        'Digital Signature URL', 
        blank=True, 
        null=True,
        help_text="Link to the e-signed document or signature verification."
    )
    
    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenancy Agreement'
        verbose_name_plural = 'Tenancy Agreements'
        ordering = ['-created_at']

    def __str__(self):
        return f"Agreement for {self.tenancy.unit.unit_code} ({self.get_status_display()})"