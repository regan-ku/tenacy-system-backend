from django.db import models

class DashboardWidget(models.Model):
    """
    Defines individual KPI widgets that can be dynamically composed 
    into role-based dashboards via the Dashboard model.
    """
    class WidgetType(models.TextChoices):
        KPI_CARD = 'kpi_card', 'KPI Card (e.g., Total Revenue)'
        CHART = 'chart', 'Chart (e.g., Occupancy Trend)'
        TABLE = 'table', 'Data Table (e.g., Recent Payments)'
        ALERT = 'alert', 'Alert List (e.g., Overdue Maintenance)'

    name = models.CharField('Widget Name', max_length=100, unique=True)
    widget_type = models.CharField(
        'Widget Type', 
        max_length=20, 
        choices=WidgetType.choices
    )
    description = models.TextField('Description', blank=True, null=True)
    
    # The aggregator service method this widget calls 
    # (e.g., 'payment_aggregator.get_total_revenue')
    data_source = models.CharField(
        'Data Source Service', 
        max_length=255,
        help_text="The backend service method that populates this widget."
    )
    
    # Configuration for the frontend to render it correctly
    frontend_config = models.JSONField(
        'Frontend Configuration',
        default=dict,
        help_text="UI settings like chart type, color, currency formatting, etc."
    )
    
    is_active = models.BooleanField('Is Active', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_widget_type_display()})"