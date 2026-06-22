from django.db import models
from django.conf import settings

class Report(models.Model):
    """
    Tracks the lifecycle of requested report generations.
    Stores parameters, status, and the final exported file URL.
    """
    class ReportType(models.TextChoices):
        FINANCIAL = 'financial', 'Financial & Revenue Report'
        OCCUPANCY = 'occupancy', 'Occupancy & Vacancy Report'
        TENANCY = 'tenancy', 'Tenancy & Tenant History Report'
        MAINTENANCE = 'maintenance', 'Maintenance & SLA Report'
        MARKETPLACE = 'marketplace', 'Marketplace & Lead Analytics'
        APPLICATIONS = 'applications', 'Application Conversion Report'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Generation'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    title = models.CharField('Report Title', max_length=255)
    report_type = models.CharField(
        'Report Type',
        max_length=20,
        choices=ReportType.choices
    )

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports',
        help_text="User who requested this report."
    )

    # Stores filters like date_range, property_ids, status filters
    parameters = models.JSONField(
        'Report Parameters',
        default=dict,
        help_text="Filters and criteria used to generate this report."
    )

    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    file_url = models.URLField(
        'Exported File URL',
        blank=True,
        null=True,
        help_text="Link to the generated PDF or Excel file in cloud storage."
    )

    error_message = models.TextField('Error Message', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Report Generation Request'
        verbose_name_plural = 'Report Generation Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'status']),
            models.Index(fields=['generated_by', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.title} ({self.get_status_display()})"