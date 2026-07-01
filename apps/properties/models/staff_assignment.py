from django.db import models
from django.conf import settings

class PropertyStaffAssignment(models.Model):
    """
    Links a User to a Property with a specific operational role.
    Handles BOTH Landlord-assigned caretakers AND Agency-assigned staff,
    as well as Tenants assigned as Resident Caretakers.
    """
    class OperationalRole(models.TextChoices):
        CARETAKER = 'caretaker', 'Caretaker'
        AGENT = 'agent', 'Agent'
        PROPERTY_MANAGER = 'property_manager', 'Property Manager'

    class AssignmentSource(models.TextChoices):
        LANDLORD = 'landlord', 'Direct Landlord Assignment'
        AGENCY = 'agency', 'Agency Assignment'

    property = models.ForeignKey(
        'Property',
        on_delete=models.CASCADE,
        related_name='staff_assignments',
        help_text="The property this staff member is assigned to."
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='property_assignments',
        help_text="The user performing the operational role."
    )
    
    operational_role = models.CharField(
        'Operational Role',
        max_length=30,
        choices=OperationalRole.choices
    )
    
    assigned_by_entity_type = models.CharField(
        'Assigned By',
        max_length=20,
        choices=AssignmentSource.choices,
        default=AssignmentSource.LANDLORD,
        help_text="Tracks whether the landlord or the agency made this assignment."
    )
    
    assigned_by_agency = models.ForeignKey(
        'agencies.Agency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='property_staff_assignments',
        help_text="The agency that made this assignment (if applicable)."
    )
    
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Property Staff Assignment'
        verbose_name_plural = 'Property Staff Assignments'
        constraints = [
            # Prevents a user from having the same active role on the same property twice
            models.UniqueConstraint(
                fields=['property', 'user', 'operational_role'],
                condition=models.Q(is_active=True),
                name='unique_active_role_per_property_user'
            )
        ]
        indexes = [
            models.Index(fields=['property', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} as {self.get_operational_role_display()} at {self.property.title}"

    def terminate(self):
        """Helper method to cleanly terminate an assignment."""
        from django.utils import timezone
        self.is_active = False
        self.terminated_at = timezone.now()
        self.save(update_fields=['is_active', 'terminated_at'])