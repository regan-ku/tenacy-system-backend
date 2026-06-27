from django.db import models
from django.conf import settings

class Tenancy(models.Model):
    """
    Represents the active relationship between a tenant and a specific unit.
    """
    class TenancyType(models.TextChoices):
        RENTAL = 'rental', 'Rental'
        LEASE = 'lease', 'Lease'

    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        EXTENDED = 'extended', 'Extended'
        # ✅ CRITICAL FIX: Added Scheduled for Termination status
        SCHEDULED_FOR_TERMINATION = 'scheduled_for_termination', 'Scheduled for Termination' 
        TERMINATED = 'terminated', 'Terminated'
        TRANSFERRED = 'transferred', 'Transferred'
        EXPIRED = 'expired', 'Expired'

    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='tenancies')
    unit = models.ForeignKey('properties.Unit', on_delete=models.PROTECT, related_name='tenancies')
    property = models.ForeignKey('properties.Property', on_delete=models.PROTECT, related_name='tenancies')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tenancies')

    tenancy_type = models.CharField(max_length=20, choices=TenancyType.choices, default=TenancyType.RENTAL)

    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    service_charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    deposit_paid = models.BooleanField(default=False)
    service_charge_paid = models.BooleanField(default=False)
    deposit_waived = models.BooleanField(default=False)
    service_charge_waived = models.BooleanField(default=False)

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING_PAYMENT) # Increased max_length to 30
    
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    
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
        constraints = [
            models.UniqueConstraint(
                fields=['unit'],
                # ✅ FIX: Include 'scheduled_for_termination' so a unit can't be double-booked while waiting to vacate
                condition=models.Q(status__in=['active', 'pending_payment', 'extended', 'scheduled_for_termination']),
                name='unique_active_tenancy_per_unit'
            )
        ]

    def __str__(self):
        return f"{self.tenant.email} - {self.unit.unit_code} ({self.get_status_display()})"

    def is_ready_for_activation(self) -> bool:
        deposit_settled = self.deposit_paid or self.deposit_waived
        service_charge_settled = self.service_charge_paid or self.service_charge_waived
        return deposit_settled and service_charge_settled