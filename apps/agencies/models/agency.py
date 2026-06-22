from django.db import models
from django.conf import settings

class Agency(models.Model):
    """
    Core Agency entity representing a registered property management company.
    """
    class Status(models.TextChoices):
        PENDING_VERIFICATION = 'pending_verification', 'Pending Verification'
        VERIFIED = 'verified', 'Verified'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        REJECTED = 'rejected', 'Rejected'

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_agencies',
        help_text="The user who initially registered this agency."
    )
    
    name = models.CharField('Agency Name', max_length=255, unique=True)
    registration_number = models.CharField(
        'Business Registration Number', 
        max_length=100, 
        unique=True,
        help_text="Official government registration number."
    )
    
    contact_email = models.EmailField('Contact Email', unique=True)
    phone_number = models.CharField('Contact Phone', max_length=15)
    physical_address = models.TextField('Physical Address')
    
    status = models.CharField(
        'Status', 
        max_length=30, 
        choices=Status.choices, 
        default=Status.PENDING_VERIFICATION
    )
    
    is_active = models.BooleanField('Is Active', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agency'
        verbose_name_plural = 'Agencies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['registration_number']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Auto-lowercase email to prevent duplicates
        if self.contact_email:
            self.contact_email = self.contact_email.lower()
        super().save(*args, **kwargs)