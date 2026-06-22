from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.accounts.utils.validators import validate_kra_pin

class AgencyVerification(models.Model):
    """
    Tracks business-level verification for an agency.
    Includes Business Registration, KRA PIN, Tax Compliance, and Agency Licenses.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'
        RESUBMIT = 'resubmit', 'Resubmission Required'

    agency = models.OneToOneField(
        'Agency',
        on_delete=models.CASCADE,
        related_name='verification_record',
        help_text="The agency being verified."
    )
    
    # Business Documents
    business_registration_cert = models.FileField(
        'Business Registration Certificate', 
        upload_to='agencies/verifications/business_reg/', 
        blank=True, 
        null=True
    )
    
    kra_pin = models.CharField(
        'Business KRA PIN', 
        max_length=11, 
        blank=True, 
        null=True,
        validators=[validate_kra_pin],
        help_text="Format: A012345678B"
    )
    
    kra_tax_compliance_cert = models.FileField(
        'KRA Tax Compliance Certificate', 
        upload_to='agencies/verifications/tax/', 
        blank=True, 
        null=True
    )
    
    agency_license = models.FileField(
        'Estate Agents Registration Board (EARB) License', 
        upload_to='agencies/verifications/licenses/', 
        blank=True, 
        null=True,
        help_text="Official agency operating license."
    )

    # Workflow State
    status = models.CharField(
        'Verification Status', 
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    
    submitted_at = models.DateTimeField('Submitted At', auto_now_add=True)
    reviewed_at = models.DateTimeField('Reviewed At', blank=True, null=True)
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_verifications_reviewed',
        help_text="Admin who reviewed this verification."
    )
    
    rejection_reason = models.TextField('Rejection/Resubmission Reason', blank=True, null=True)

    class Meta:
        verbose_name = 'Agency Verification'
        verbose_name_plural = 'Agency Verifications'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['agency', 'status']),
        ]

    def __str__(self):
        return f"Verification: {self.agency.name} ({self.status})"

    def mark_verified(self, reviewer):
        """Helper method to approve agency verification and activate the agency."""
        self.status = self.Status.VERIFIED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.agency.status = self.agency.Status.VERIFIED
        self.agency.is_active = True
        self.agency.save(update_fields=['status', 'is_active'])
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def mark_rejected(self, reviewer, reason):
        """Helper method to reject agency verification."""
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.agency.status = self.agency.Status.REJECTED
        self.agency.is_active = False
        self.agency.save(update_fields=['status', 'is_active'])
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])