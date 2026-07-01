from django.db import models
from django.utils import timezone

class DelegatedProperty(models.Model):
    """
    The core delegation model linking an Agency to a Property.
    
    ARCHITECTURAL RULE: DELEGATION IS STRICTLY "FULL OR NONE".
    If this record exists and status is ACTIVE, the Agency has 100% operational control.
    The Landlord is reduced to a read-only financial viewer.
    If this record does not exist (or is revoked), the Landlord retains full control.
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active (Full Control Transferred)'
        REVOKED = 'revoked', 'Revoked by Landlord'
        EXPIRED = 'expired', 'Contract Expired'
        PENDING = 'pending', 'Pending Agency Acceptance'

    property_ref = models.ForeignKey(
        'properties.Property', 
        on_delete=models.CASCADE,
        related_name='agency_delegations',
        help_text="The property being fully delegated."
    )
    
    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='delegated_properties',
        help_text="The agency receiving 100% management rights."
    )
    
    status = models.CharField(
        'Delegation Status', 
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    
    start_date = models.DateField('Start Date')
    end_date = models.DateField('End Date', blank=True, null=True)
    
    revoked_at = models.DateTimeField('Revoked At', blank=True, null=True)
    revoked_by = models.ForeignKey(
        'accounts.User', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_delegations',
        help_text="User who revoked this delegation."
    )
    revocation_reason = models.TextField('Revocation Reason', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delegated Property'
        verbose_name_plural = 'Delegated Properties'
        constraints = [
            # Ensures an agency can only have ONE active full delegation per property
            models.UniqueConstraint(
                fields=['property_ref', 'agency'],
                condition=models.Q(status='active'),
                name='unique_active_delegation_per_property_agency'
            )
        ]
        indexes = [
            models.Index(fields=['agency', 'status']),
            models.Index(fields=['property_ref', 'status']),
        ]

    def __str__(self):
        return f"{self.property_ref.title} → {self.agency.name} ({self.get_status_display()})"

    def revoke(self, user, reason=""):
        """Helper method to cleanly revoke full delegation."""
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.revocation_reason = reason
        self.save(update_fields=['status', 'revoked_at', 'revoked_by', 'revocation_reason'])