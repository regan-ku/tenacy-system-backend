from django.db import models
from django.conf import settings

class AgencyStaff(models.Model):
    """
    Represents internal staff members (Agents, Caretakers, Admins) 
    employed by or contracted to an Agency.
    """
    class StaffRole(models.TextChoices):
        PROPERTY_MANAGER = 'property_manager', 'Property Manager'
        FIELD_AGENT = 'field_agent', 'Field Agent'
        MAINTENANCE_SUPERVISOR = 'maintenance_supervisor', 'Maintenance Supervisor'
        OPERATIONS_ADMIN = 'operations_admin', 'Operations Admin'
        CARETAKER = 'caretaker', 'Caretaker'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        TERMINATED = 'terminated', 'Terminated'

    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='staff_members',
        help_text="The agency this staff member belongs to."
    )
    
    # Links to the actual User account. If null, they are a pending invite.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_staff_profiles',
        help_text="Linked system user account."
    )
    
    role = models.CharField(
        'Staff Role', 
        max_length=30, 
        choices=StaffRole.choices
    )
    
    status = models.CharField(
        'Employment Status', 
        max_length=20, 
        choices=Status.choices, 
        default=Status.ACTIVE
    )
    
    # Optional: Direct phone/email for staff who haven't created an account yet
    contact_phone = models.CharField('Contact Phone', max_length=15, blank=True, null=True)
    contact_email = models.EmailField('Contact Email', blank=True, null=True)
    
    joined_at = models.DateTimeField('Joined At', auto_now_add=True)
    terminated_at = models.DateTimeField('Terminated At', blank=True, null=True)
    notes = models.TextField('Internal Notes', blank=True, null=True)

    class Meta:
        verbose_name = 'Agency Staff Member'
        verbose_name_plural = 'Agency Staff Members'
        constraints = [
            models.UniqueConstraint(
                fields=['agency', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_staff_user_per_agency'
            )
        ]
        indexes = [
            models.Index(fields=['agency', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        user_email = self.user.email if self.user else (self.contact_email or "Pending Invite")
        return f"{user_email} ({self.get_role_display()}) - {self.agency.name}"

    def save(self, *args, **kwargs):
        if self.contact_email:
            self.contact_email = self.contact_email.lower()
        
        if self.status == self.Status.TERMINATED and not self.terminated_at:
            from django.utils import timezone
            self.terminated_at = timezone.now()
            
        super().save(*args, **kwargs)