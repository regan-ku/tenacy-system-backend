from django.db import models
from .enums import UnitType, UnitStatus, BillingCycle
from .property import Property
from .unit_group import UnitGroup

class Unit(models.Model):
    """
    Represents an individual rentable/sellable unit within a property.
    Inherits rules (pets, parking, currency) directly from the parent Property.
    """
    property_ref = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='units',
        help_text="The parent property."
    )
    
    unit_group = models.ForeignKey(
        UnitGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='units',
        help_text="The group this unit belongs to (Null for single-unit properties)."
    )
    
    cover_photo = models.ImageField(
        'Unit Cover Photo', 
        upload_to='units/covers/', 
        blank=True, 
        null=True,
        help_text="Main display image for this specific unit."
    )
    
    unit_code = models.CharField('Unit Code', max_length=50, unique=True, help_text="e.g., 'A-101', 'MANSION-01'")
    unit_type = models.CharField('Unit Type', max_length=30, choices=UnitType.choices)
    floor_number = models.PositiveIntegerField('Floor Number', default=1)
    
    rent_amount = models.DecimalField('Rent Amount', max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField('Deposit Amount', max_digits=10, decimal_places=2, default=0.00)
    service_charge = models.DecimalField('Service Charge', max_digits=10, decimal_places=2, default=0.00)
    
    billing_cycle = models.CharField('Billing Cycle', max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    billing_date = models.PositiveIntegerField('Billing Date', default=5, help_text="Day rent is due.")
    
    status = models.CharField('Status', max_length=20, choices=UnitStatus.choices, default=UnitStatus.AVAILABLE)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'
        ordering = ['property_ref', 'unit_code']  # <-- FIXED
        indexes = [
            models.Index(fields=['property_ref', 'status']),  # <-- FIXED
            models.Index(fields=['unit_group', 'status']),
        ]

    def __str__(self):
        return f"{self.unit_code} - {self.property_ref.title}"  # <-- FIXED

    # --- INHERITANCE PROPERTIES (For clean API serialization without DB duplication) ---
    @property
    def allows_pets(self):
        return self.property_ref.allows_pets  # <-- FIXED

    @property
    def parking_spaces(self):
        return self.property_ref.parking_spaces  # <-- FIXED