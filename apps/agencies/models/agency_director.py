from django.db import models
from django.conf import settings
from apps.accounts.utils.validators import (
    validate_national_id, 
    validate_phone_number, 
    validate_strict_email
)

class AgencyDirector(models.Model):
    """
    Legally responsible individuals within an agency.
    Required for agency activation and compliance.
    """
    class VerificationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'
        SUSPENDED = 'suspended', 'Suspended'

    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='directors',
        help_text="The agency this director belongs to."
    )
    
    # Link to a system user if the director also has an account, otherwise null
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='director_profiles',
        help_text="Linked system user (if the director has an account)."
    )
    
    full_name = models.CharField('Full Name', max_length=255)
    
    national_id = models.CharField(
        'National ID', 
        max_length=8, 
        blank=True, 
        null=True,
        validators=[validate_national_id],
        help_text="7 or 8 digit National ID."
    )
    
    passport_number = models.CharField(
        'Passport Number', 
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Alternative to National ID."
    )
    
    email = models.EmailField('Email', validators=[validate_strict_email])
    phone_number = models.CharField(
        'Phone Number', 
        max_length=15, 
        validators=[validate_phone_number]
    )
    
    nationality = models.CharField('Nationality', max_length=100)
    address = models.TextField('Residential Address')
    
    ownership_percentage = models.DecimalField(
        'Ownership Percentage', 
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Percentage of agency ownership (0.00 - 100.00)."
    )
    
    is_primary_director = models.BooleanField('Primary Director', default=False)
    
    verification_status = models.CharField(
        'Verification Status', 
        max_length=20, 
        choices=VerificationStatus.choices, 
        default=VerificationStatus.PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agency Director'
        verbose_name_plural = 'Agency Directors'
        constraints = [
            models.CheckConstraint(
                check=models.Q(national_id__isnull=False) | models.Q(passport_number__isnull=False),
                name='director_must_have_id_or_passport'
            )
        ]
        indexes = [
            models.Index(fields=['agency', 'verification_status']),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.agency.name}"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
            
        # Ensure only one primary director per agency
        if self.is_primary_director:
            AgencyDirector.objects.filter(
                agency=self.agency, 
                is_primary_director=True
            ).exclude(pk=self.pk).update(is_primary_director=False)
            
        super().save(*args, **kwargs)