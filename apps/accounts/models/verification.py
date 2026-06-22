from django.db import models
from django.conf import settings
from django.utils import timezone
from ..utils.validators import validate_kra_pin

class Verification(models.Model):
    """
    Handles personal identity and tax verification workflows for individual users.
    Specifically targets Landlords who must prove their personal identity and tax compliance.
    
    ARCHITECTURAL BOUNDARIES:
    - Proof of Ownership (Title Deeds) is handled in the 'properties' app during property creation.
    - Business Registration, Licenses, and Director IDs are handled in the 'agencies' app.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('resubmit', 'Resubmission Required'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_record',
        help_text="The user being verified."
    )

    # 1. Personal Identity Documents (Required for Landlords)
    id_document_front = models.FileField(
        'ID/Passport Front', 
        upload_to='verifications/ids/', 
        blank=True, 
        null=True,
        help_text="Clear photo of National ID or Passport front."
    )
    id_document_back = models.FileField(
        'ID/Passport Back', 
        upload_to='verifications/ids/', 
        blank=True, 
        null=True,
        help_text="Clear photo of National ID back (if applicable)."
    )

    # 2. Personal Tax Compliance (Required for Landlords)
    kra_pin = models.CharField(
        'Personal KRA PIN', 
        max_length=11, 
        blank=True, 
        null=True,
        validators=[validate_kra_pin],
        help_text="Format: A012345678B"
    )
    kra_tax_compliance_cert = models.FileField(
        'KRA Tax Compliance Certificate', 
        upload_to='verifications/tax/', 
        blank=True, 
        null=True,
        help_text="Valid, up-to-date KRA Tax Compliance Certificate."
    )

    # Workflow State
    status = models.CharField(
        'Verification Status', 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    
    submitted_at = models.DateTimeField('Submitted At', auto_now_add=True)
    reviewed_at = models.DateTimeField('Reviewed At', blank=True, null=True)
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verifications_reviewed',
        help_text="Admin who reviewed this verification."
    )
    
    rejection_reason = models.TextField('Rejection/Resubmission Reason', blank=True, null=True)

    class Meta:
        verbose_name = 'User Verification'
        verbose_name_plural = 'User Verifications'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"Verification: {self.user.email} ({self.status})"

    def mark_verified(self, reviewer):
        """Helper method to approve verification and update user state."""
        self.status = 'verified'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def mark_rejected(self, reviewer, reason):
        """Helper method to reject verification and require resubmission."""
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.user.is_verified = False
        self.user.save(update_fields=['is_verified'])
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])