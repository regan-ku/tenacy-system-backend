from django.db import models
from django.conf import settings

class ReportSchedule(models.Model):
    """
    Allows authorized users to schedule recurring report generations.
    Managed by Celery Beat to trigger report creation automatically.
    """
    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        YEARLY = 'yearly', 'Yearly'

    title = models.CharField('Schedule Title', max_length=255)
    report_type = models.CharField(
        'Report Type',
        max_length=20,
        choices=[
            ('financial', 'Financial & Revenue Report'),
            ('occupancy', 'Occupancy & Vacancy Report'),
            ('tenancy', 'Tenancy & Tenant History Report'),
            ('maintenance', 'Maintenance & SLA Report'),
        ]
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='scheduled_reports',
        help_text="User who configured this schedule."
    )

    frequency = models.CharField(
        'Frequency',
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.MONTHLY
    )

    # Stores filters like date_range, property_ids, status filters for the recurring run
    parameters = models.JSONField(
        'Report Parameters',
        default=dict,
        help_text="Filters and criteria applied to every scheduled run."
    )

    is_active = models.BooleanField('Is Active', default=True)
    next_run_at = models.DateTimeField('Next Run At', blank=True, null=True)
    last_run_at = models.DateTimeField('Last Run At', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Report Schedule'
        verbose_name_plural = 'Report Schedules'
        ordering = ['-next_run_at']
        indexes = [
            models.Index(fields=['is_active', 'next_run_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_frequency_display()})"