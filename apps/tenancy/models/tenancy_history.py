from django.db import models
from django.conf import settings

class TenancyHistory(models.Model):
    """
    Immutable record of a completed or terminated tenancy.
    Used for tenant background checks, landlord reporting, and system analytics.
    """
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='tenancy_history_records'
    )
    unit = models.ForeignKey(
        'properties.Unit',
        on_delete=models.PROTECT,
        related_name='tenancy_history_records'
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='tenancy_history_records'
    )
    
    tenancy_type = models.CharField('Tenancy Type', max_length=20)
    start_date = models.DateField('Start Date')
    end_date = models.DateField('End Date')
    final_status = models.CharField('Final Status', max_length=50) # e.g., 'terminated', 'expired', 'transferred'
    
    termination_reason = models.TextField('Termination Reason', blank=True, null=True)
    manager_notes = models.TextField('Manager Notes', blank=True, null=True)
    
    # Future: Used for AI risk scoring or landlord references
    performance_score = models.PositiveIntegerField(
        'Performance Score', 
        blank=True, 
        null=True, 
        help_text="1-100 score based on payment timeliness and property care."
    )
    
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tenancy History Record'
        verbose_name_plural = 'Tenancy History Records'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['tenant', 'recorded_at']),
            models.Index(fields=['property', 'recorded_at']),
        ]

    def __str__(self):
        return f"History: {self.tenant.email} at {self.unit.unit_code} ({self.start_date} to {self.end_date})"