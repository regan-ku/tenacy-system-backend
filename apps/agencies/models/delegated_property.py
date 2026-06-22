from django.db import models
from django.utils import timezone

class DelegatedProperty(models.Model):
    """
    The core delegation model linking an Agency to a Property.
    Defines the scope of operational control the agency has over the property.
    """
    class DelegationType(models.TextChoices):
        FULL = 'full', 'Full Delegation (Tenants, Payments, Maintenance, Operations)'
        PARTIAL = 'partial', 'Partial Delegation (e.g., Maintenance & Tenants only)'
        VIEW_ONLY = 'view_only', 'View Only (Assistance & Reporting)'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        REVOKED = 'revoked', 'Revoked by Landlord'
        EXPIRED = 'expired', 'Contract Expired'
        PENDING = 'pending', 'Pending Agency Acceptance'

    property_ref = models.ForeignKey(
        'properties.Property', # String reference to avoid circular import with properties app
        on_delete=models.CASCADE,
        related_name='agency_delegations',
        help_text="The property being delegated."
    )
    
    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='delegated_properties',
        help_text="The agency receiving delegation rights."
    )
    
    delegation_type = models.CharField(
        'Delegation Type', 
        max_length=20, 
        choices=DelegationType.choices,
        default=DelegationType.PARTIAL
    )
    
    # Granular permissions override (JSON). If empty, defaults to delegation_type rules.
    # Example: {"manage_tenants": true, "collect_payments": false, "manage_maintenance": true}
    custom_permissions = models.JSONField(
        'Custom Permissions', 
        default=dict, 
        blank=True,
        help_text="Specific permission overrides for this delegation."
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
        'accounts.User', # String reference to accounts app
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
        """Helper method to cleanly revoke delegation."""
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.revocation_reason = reason
        self.save(update_fields=['status', 'revoked_at', 'revoked_by', 'revocation_reason'])