from django.db import models
from django.conf import settings

class Dashboard(models.Model):
    """
    Defines the blueprint and configuration for role-based dashboards.
    Ensures each user type sees only their authorized KPIs and data scopes.
    """
    class RoleType(models.TextChoices):
        ADMIN = 'admin', 'System Administrator'
        LANDLORD = 'landlord', 'Landlord'
        AGENCY = 'agency', 'Agency'
        AGENT = 'agent', 'Agent'
        CARETAKER = 'caretaker', 'Caretaker'
        TENANT = 'tenant', 'Tenant'

    role = models.CharField(
        'Target Role',
        max_length=20,
        choices=RoleType.choices,
        unique=True,
        help_text="The user role this dashboard configuration applies to."
    )

    name = models.CharField('Dashboard Name', max_length=100)
    description = models.TextField('Description', blank=True, null=True)
    
    # JSON field to store the layout, enabled widgets, and default date ranges for this role
    widget_configuration = models.JSONField(
        'Widget Configuration',
        default=dict,
        help_text="Defines which KPIs, charts, and tables are visible to this role."
    )

    is_active = models.BooleanField('Is Active', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dashboard Configuration'
        verbose_name_plural = 'Dashboard Configurations'
        ordering = ['role']

    def __str__(self):
        return f"{self.get_role_display()} Dashboard"