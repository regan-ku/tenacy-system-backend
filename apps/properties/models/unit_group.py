from django.db import models
from .enums import UnitType, BillingCycle
from .property import Property

class UnitGroup(models.Model):
    """
    Defines logical groupings of units with shared billing/pricing defaults.
    Enables bulk unit generation and consistent billing rules.
    """
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='unit_groups',
        help_text="The parent property this group belongs to."
    )
    
    name = models.CharField(
        'Group Name / Prefix', 
        max_length=100, 
        help_text="e.g., 'Block A', 'Wing 1'. Used to prefix unit codes."
    )
    description = models.TextField('Description', blank=True, null=True)
    
    unit_type = models.CharField('Unit Type', max_length=30, choices=UnitType.choices)
    
    floor_range = models.CharField(
        'Floor Range', 
        max_length=50, 
        help_text="e.g., 'Ground', '1-3', '4-5'."
    )
    
    billing_cycle = models.CharField('Billing Cycle', max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    
    billing_date = models.PositiveIntegerField(
        'Billing Date', 
        default=5, 
        help_text="Day of the month/week rent is due."
    )
    
    # Financial Defaults
    base_rent_amount = models.DecimalField('Base Rent', max_digits=10, decimal_places=2)
    service_charge = models.DecimalField('Service Charge', max_digits=10, decimal_places=2, default=0.00)
    deposit_amount = models.DecimalField('Security Deposit', max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField('Currency', max_length=3, default='KES')
    
    capacity = models.PositiveIntegerField('Total Units in Group', default=1)
    allows_pets_override = models.BooleanField('Pets Allowed (Override Property)', null=True, blank=True)
    
    # ✅ NEW: Cover Photo for the Unit Group
    cover_photo = models.ImageField(
        'Group Cover Photo', 
        upload_to='properties/unit_groups/covers/%Y/%m/', 
        blank=True, 
        null=True,
        help_text="Primary thumbnail for this unit group."
    )
    
    is_active = models.BooleanField('Is Active', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Unit Group'
        verbose_name_plural = 'Unit Groups'
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'name'],
                name='unique_unit_group_per_property'
            )
        ]
        indexes = [
            models.Index(fields=['property', 'is_active']),
            models.Index(fields=['billing_cycle', 'unit_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.property.title})"

    def get_effective_pets_policy(self):
        if self.allows_pets_override is not None:
            return self.allows_pets_override
        return self.property.allows_pets