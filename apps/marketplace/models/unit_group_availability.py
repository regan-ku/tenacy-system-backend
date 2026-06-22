from django.db import models

class UnitGroupAvailability(models.Model):
    """
    Tracks real-time availability of unit groups in the marketplace.
    Automatically hides the group from the marketplace when available_units == 0.
    """
    unit_group = models.OneToOneField(
        'properties.UnitGroup',
        on_delete=models.CASCADE,
        related_name='marketplace_availability'
    )
    
    total_units = models.PositiveIntegerField(
        'Total Units in Group',
        help_text="Total capacity of this unit group"
    )
    
    available_units = models.PositiveIntegerField(
        'Available Units',
        help_text="Number of units currently available for rent"
    )
    
    occupied_units = models.PositiveIntegerField('Occupied Units', default=0)
    reserved_units = models.PositiveIntegerField('Reserved Units', default=0, help_text="Pending applications")
    
    is_marketplace_visible = models.BooleanField(
        'Visible in Marketplace',
        default=True,
        help_text="Auto-set to False when available_units = 0"
    )
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Unit Group Availability'
        verbose_name_plural = 'Unit Group Availabilities'
        indexes = [
            models.Index(fields=['is_marketplace_visible', 'available_units']),
        ]
    
    def __str__(self):
        return f"{self.unit_group.name} - {self.available_units} available"
    
    def save(self, *args, **kwargs):
        # CRITICAL RULE: Auto-hide if no units are available
        if self.available_units == 0:
            self.is_marketplace_visible = False
        else:
            self.is_marketplace_visible = True
            
        # Calculate occupied units dynamically
        self.occupied_units = self.total_units - self.available_units - self.reserved_units
        
        super().save(*args, **kwargs)
    
    def get_availability_text(self):
        """Returns the exact text to display on the frontend (e.g., '3 units remaining')"""
        if self.available_units == 0:
            return "Fully Occupied"
        elif self.available_units == 1:
            return "1 unit remaining"
        else:
            return f"{self.available_units} units remaining"