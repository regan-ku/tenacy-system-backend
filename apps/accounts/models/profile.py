from django.db import models
from django.conf import settings
from ..utils.validators import validate_national_id

class Profile(models.Model):
    """
    Extended user information separate from authentication data.
    One-to-One relationship with the User model.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    full_name = models.CharField('Full Name', max_length=255, blank=True, null=True)
    
    national_id = models.CharField(
        'National ID', 
        max_length=8, 
        unique=True, 
        blank=True, 
        null=True,
        validators=[validate_national_id],
        help_text="7 or 8 digit National ID number (Required for Landlords/Agencies)."
    )
    
    nationality = models.CharField('Nationality', max_length=100, blank=True, null=True)
    address = models.TextField('Physical Address', blank=True, null=True)
    date_of_birth = models.DateField('Date of Birth', blank=True, null=True)
    
    profile_photo = models.ImageField(
        'Profile Photo', 
        upload_to='profiles/photos/', 
        blank=True, 
        null=True
    )
    
    # Tracks if the user has completed the mandatory onboarding wizard
    profile_complete = models.BooleanField('Profile Complete', default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        indexes = [
            models.Index(fields=['user', 'profile_complete']),
        ]

    def __str__(self):
        return f"Profile: {self.user.email}"

    def save(self, *args, **kwargs):
        """
        The completeness of a profile is explicitly managed by the UserService 
        based on the specific role's workflow. 
        """
        super().save(*args, **kwargs)