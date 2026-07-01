from django.db import models
from django.conf import settings

class AgencyStaff(models.Model):
    """
    Represents staff members (Agents, Caretakers, Property Managers).
    Can be employed by an Agency OR assigned directly by a Landlord (for Caretakers).
    """
    class StaffRole(models.TextChoices):
        PROPERTY_MANAGER = 'property_manager', 'Property Manager' # Agency Only
        AGENT = 'agent', 'Agent' # Agency Only
        CARETAKER = 'caretaker', 'Caretaker' # Landlord & Agency

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        TERMINATED = 'terminated', 'Terminated'

    # ✅ UPDATED: Null allowed if created directly by a Landlord
    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='staff_members',
        null=True,
        blank=True,
        help_text="The agency this staff member belongs to. Null if assigned directly by a landlord."
    )
    
    # ✅ UPDATED: User is now strictly required. Staff cannot exist without an account.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profiles',
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
        verbose_name = 'Staff Member'
        verbose_name_plural = 'Staff Members'
        # ✅ UPDATED: Removed the complex unique constraint that breaks when agency is null.
        indexes = [
            models.Index(fields=['agency', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['role', 'status']), # ✅ Added for fast role filtering
        ]

    def __str__(self):
        user_email = self.user.email if self.user else (self.contact_email or "Pending Invite")
        agency_name = self.agency.name if self.agency else "Direct Landlord Assignment"
        return f"{user_email} ({self.get_role_display()}) - {agency_name}"

    def save(self, *args, **kwargs):
        if self.contact_email:
            self.contact_email = self.contact_email.lower()
        
        if self.status == self.Status.TERMINATED and not self.terminated_at:
            from django.utils import timezone
            self.terminated_at = timezone.now()
            
        super().save(*args, **kwargs)