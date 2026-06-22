from django.db import models

class AgencyRole(models.Model):
    """
    Customizable role templates within an agency.
    Allows agencies to define granular permission sets for their staff 
    beyond the default hardcoded roles.
    """
    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='custom_roles',
        help_text="The agency that owns this custom role."
    )
    
    name = models.CharField('Role Name', max_length=100)
    description = models.TextField('Role Description', blank=True, null=True)
    
    # JSONField to store granular permission flags (e.g., {"can_manage_tenants": true, "can_view_financials": false})
    permissions = models.JSONField(
        'Granted Permissions', 
        default=dict,
        help_text="Dictionary of granular permissions granted to this role."
    )
    
    is_active = models.BooleanField('Is Active', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Custom Agency Role'
        verbose_name_plural = 'Custom Agency Roles'
        constraints = [
            models.UniqueConstraint(
                fields=['agency', 'name'],
                name='unique_role_name_per_agency'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.agency.name})"