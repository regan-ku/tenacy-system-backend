from django.db import models
from django.conf import settings

class TenancyTransfer(models.Model):
    """
    Handles the workflow of a tenant moving from one unit/property to another.
    Ensures proper validation, approval, and occupancy updates.
    """
    class TransferStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='transfer_requests',
        help_text="The tenant requesting the transfer."
    )

    # Source
    from_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='outgoing_transfers'
    )
    from_unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        related_name='outgoing_transfers'
    )

    # Destination
    to_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='incoming_transfers'
    )
    to_unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        related_name='incoming_transfers'
    )

    reason = models.TextField('Reason for Transfer', blank=True, null=True)
    
    # ✅ NEW FIELDS: Move-in date and manager notes
    requested_move_in_date = models.DateField(
        'Requested Move-in Date',
        null=True,
        blank=True,
        help_text="When the tenant wants to move into the new unit."
    )
    
    manager_notes = models.TextField(
        'Manager Notes',
        blank=True,
        null=True,
        help_text="Additional notes from the requesting manager/agent for the approving manager."
    )
    
    transfer_status = models.CharField(
        'Transfer Status',
        max_length=20,
        choices=TransferStatus.choices,
        default=TransferStatus.PENDING
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_transfers'
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transfers',
        help_text="Manager or landlord who approved the transfer."
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Tenancy Transfer'
        verbose_name_plural = 'Tenancy Transfers'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['tenant', 'transfer_status']),
        ]

    def __str__(self):
        return f"Transfer: {self.tenant.email} from {self.from_unit.unit_code} to {self.to_unit.unit_code}"