from django.db import models
from django.conf import settings

class AgencyPermission(models.Model):
    """
    Granular, explicit permissions granted to a specific staff member 
    for a specific scope (e.g., specific properties or global agency access).
    """
    class PermissionScope(models.TextChoices):
        GLOBAL = 'global', 'Global Agency Access'
        PROPERTY_SPECIFIC = 'property_specific', 'Specific Delegated Properties'

    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='staff_permissions'
    )
    
    staff_member = models.ForeignKey(
        'AgencyStaff',
        on_delete=models.CASCADE,
        related_name='explicit_permissions',
        help_text="The staff member receiving these permissions."
    )
    
    scope = models.CharField(
        'Permission Scope',
        max_length=30,
        choices=PermissionScope.choices,
        default=PermissionScope.GLOBAL
    )
    
    # If scope is PROPERTY_SPECIFIC, this links to the delegated property
    delegated_property = models.ForeignKey(
        'DelegatedProperty',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff_permissions'
    )
    
    # JSON field storing explicit boolean flags (e.g., {"can_approve_maintenance": true, "can_view_rent_roll": false})
    permissions = models.JSONField(
        'Granted Permissions',
        default=dict,
        help_text="Explicit permission overrides for this staff member."
    )
    
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_agency_permissions'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agency Staff Permission'
        verbose_name_plural = 'Agency Staff Permissions'
        constraints = [
            models.UniqueConstraint(
                fields=['staff_member', 'scope', 'delegated_property'],
                name='unique_permission_per_staff_scope_property'
            )
        ]

    def __str__(self):
        return f"Permissions for {self.staff_member} ({self.scope})"