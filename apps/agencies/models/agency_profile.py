from django.db import models
from apps.accounts.utils.validators import validate_kra_pin, validate_phone_number, validate_strict_email

class AgencyProfile(models.Model):
    """
    Business-level profile for an Agency.
    Used when the Agency itself acts as a Tenant (e.g., renting office space) 
    or when the Tenancy/Application apps require corporate entity details.
    """
    agency = models.OneToOneField(
        'Agency',
        on_delete=models.CASCADE,
        related_name='business_profile',
        help_text="The agency this profile belongs to."
    )
    
    # Core Business Identity
    business_name = models.CharField('Registered Business Name', max_length=255)
    registration_number = models.CharField(
        'Business Registration Number', 
        max_length=100, 
        unique=True
    )
    kra_pin = models.CharField(
        'Business KRA PIN', 
        max_length=11, 
        unique=True,
        validators=[validate_kra_pin],
        help_text="Format: A012345678B"
    )
    
    # Business Contact & Location
    physical_address = models.TextField('Registered Physical Address')
    postal_code = models.CharField('Postal Code', max_length=20, blank=True, null=True)
    city = models.CharField('City', max_length=100)
    county = models.CharField('County', max_length=100)
    
    # Primary Contact Person (The human representing the business)
    contact_person_name = models.CharField('Contact Person Name', max_length=255)
    contact_person_phone = models.CharField(
        'Contact Phone', 
        max_length=15, 
        validators=[validate_phone_number]
   )
    contact_person_email = models.EmailField(
        'Contact Email', 
        validators=[validate_strict_email]
    )
    
    is_profile_complete = models.BooleanField('Profile Complete', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agency Business Profile'
        verbose_name_plural = 'Agency Business Profiles'

    def __str__(self):
        return f"Profile: {self.business_name}"

    def save(self, *args, **kwargs):
        # Auto-evaluate completeness based on mandatory tenancy fields
        required_fields = [
            self.business_name, self.registration_number, self.kra_pin,
            self.physical_address, self.city, self.county,
            self.contact_person_name, self.contact_person_phone, self.contact_person_email
        ]
        self.is_profile_complete = all(bool(field) for field in required_fields)
        
        if self.contact_person_email:
            self.contact_person_email = self.contact_person_email.lower()
            
        super().save(*args, **kwargs)