from django.db import models

class TransferApplication(models.Model):
    """
    Extends the base Application model to handle tenant relocation workflows.
    Tracks the source and destination units/properties for validation.
    """
    application = models.OneToOneField(
        'Application',
        on_delete=models.CASCADE,
        related_name='transfer_details',
        help_text="The base application record this transfer extends."
    )

    # Source (Current) Tenancy Context
    current_tenancy = models.ForeignKey(
        'tenancy.Tenancy',
        on_delete=models.PROTECT,
        related_name='outgoing_transfer_requests',
        help_text="The active tenancy the tenant is transferring from."
    )

    from_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='outgoing_transfer_applications',
        help_text="The property the tenant is currently occupying."
    )

    from_unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        related_name='outgoing_transfer_applications',
        help_text="The specific unit the tenant is currently occupying."
    )

    # Destination Context
    to_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='incoming_transfer_applications',
        help_text="The destination property."
    )

    to_unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        related_name='incoming_transfer_applications',
        help_text="The specific destination unit."
    )

    reason = models.TextField(
        'Reason for Transfer',
        help_text="Tenant's justification for the transfer request."
    )

    # System Validation Flags (Populated by TenancyConditionService)
    has_unpaid_critical_arrears = models.BooleanField('Has Unpaid Critical Arrears', default=False)
    transfer_allowed_by_permissions = models.BooleanField('Transfer Allowed by Permissions', default=False)

    class Meta:
        verbose_name = 'Transfer Application'
        verbose_name_plural = 'Transfer Applications'

    def __str__(self):
        return f"Transfer: {self.from_unit.unit_code} → {self.to_unit.unit_code}"