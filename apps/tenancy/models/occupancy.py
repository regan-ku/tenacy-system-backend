from django.db import models
from django.conf import settings

class Occupancy(models.Model):
    """
    Tracks real-time unit occupancy status.
    This is the single source of truth for whether a unit is available in the marketplace.
    """
    unit = models.OneToOneField(
        'properties.Unit',
        on_delete=models.CASCADE,
        related_name='occupancy_record',
        help_text="The unit being tracked."
    )
    
    is_occupied = models.BooleanField('Is Occupied', default=False)
    
    current_tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_occupancies',
        help_text="The tenant currently occupying this unit."
    )
    
    active_tenancy = models.OneToOneField(
        'Tenancy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='occupancy_record',
        help_text="The active tenancy driving this occupancy."
    )
    
    occupancy_start_date = models.DateField('Occupancy Start Date', blank=True, null=True)
    occupancy_end_date = models.DateField('Occupancy End Date', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Occupancy Record'
        verbose_name_plural = 'Occupancy Records'
        indexes = [
            models.Index(fields=['unit', 'is_occupied']),
        ]

    def __str__(self):
        status = "Occupied" if self.is_occupied else "Vacant"
        return f"{self.unit.unit_code} - {status}"