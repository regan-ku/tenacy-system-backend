from django.db import models
from django.conf import settings

class Tenancy(models.Model):
    """
    Represents the active relationship between a tenant and a specific unit.
    Core entity for occupancy, lifecycle, and financial validation status.
    """
    class TenancyType(models.TextChoices):
        RENTAL = 'rental', 'Rental'
        LEASE = 'lease', 'Lease'

    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        EXTENDED = 'extended', 'Extended'
        TERMINATED = 'terminated', 'Terminated'
        TRANSFERRED = 'transferred', 'Transferred'
        EXPIRED = 'expired', 'Expired'

    # Relationships
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT, # Protect to preserve historical records
        related_name='tenancies',
        help_text="The tenant occupying the unit."
    )
    unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        related_name='tenancies',
        help_text="The specific unit being occupied."
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='tenancies',
        help_text="The parent property (denormalized for faster querying)."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tenancies',
        help_text="User who created this tenancy (tenant, manager, landlord, or agency)."
    )

    # Configuration
    tenancy_type = models.CharField(
        'Tenancy Type',
        max_length=20,
        choices=TenancyType.choices,
        default=TenancyType.RENTAL
    )

    # Financial Snapshot (Stored for historical accuracy, NOT the billing engine)
    rent_amount = models.DecimalField('Rent Amount', max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField('Deposit Amount', max_digits=10, decimal_places=2, default=0.00)
    service_charge_amount = models.DecimalField('Service Charge', max_digits=10, decimal_places=2, default=0.00)
    
    deposit_paid = models.BooleanField('Deposit Paid', default=False)
    service_charge_paid = models.BooleanField('Service Charge Paid', default=False)
    deposit_waived = models.BooleanField('Deposit Waived', default=False)
    service_charge_waived = models.BooleanField('Service Charge Waived', default=False)

    # Lifecycle
    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT
    )
    
    start_date = models.DateField('Start Date')
    end_date = models.DateField('End Date', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenancy'
        verbose_name_plural = 'Tenancies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['unit', 'status']),
            models.Index(fields=['property', 'status']),
        ]
        # CRITICAL RULE: A unit can only have ONE active tenancy at a time
        constraints = [
            models.UniqueConstraint(
                fields=['unit'],
                condition=models.Q(status__in=['active', 'pending_payment', 'extended']),
                name='unique_active_tenancy_per_unit'
            )
        ]

    def __str__(self):
        return f"{self.tenant.email} - {self.unit.unit_code} ({self.get_status_display()})"

    def is_ready_for_activation(self) -> bool:
        """
        Checks if the tenancy meets the criteria to become ACTIVE.
        Rule: Deposit AND Service Charge must be paid OR waived.
        """
        deposit_settled = self.deposit_paid or self.deposit_waived
        service_charge_settled = self.service_charge_paid or self.service_charge_waived
        return deposit_settled and service_charge_settled