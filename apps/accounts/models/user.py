from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from ..utils.validators import validate_phone_number, validate_strict_email

class UserManager(BaseUserManager):
    """
    Custom manager for User model where email is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin') # Ensure superuser gets admin role

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User Model replacing Django's default User.
    Uses Email as the primary identifier (USERNAME_FIELD).
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'System Administrator'
        LANDLORD = 'landlord', 'Landlord / Property Owner'
        AGENCY = 'agency', 'Real Estate Agency'
        AGENT = 'agent', 'Agency Agent'
        CARETAKER = 'caretaker', 'Property Caretaker'
        TENANT = 'tenant', 'Tenant'

    # Override username to make email the primary identifier
    username = None 
    
    email = models.EmailField(
        'Email Address', 
        unique=True, 
        validators=[validate_strict_email]
    )
    
    phone_number = models.CharField(
        'Phone Number', 
        max_length=25, 
        unique=True, 
        null=True,        
        blank=True,       
        validators=[validate_phone_number],
        help_text="Format: +254712345678 or 0712345678"
    )
    
    role = models.CharField(
        'User Role', 
        max_length=20, 
        choices=Role.choices, 
        default=Role.TENANT # Automatically defaults to tenant!
    )
    
    is_verified = models.BooleanField(
        'Identity Verified', 
        default=False, 
        help_text="True if user has submitted and passed ID/KRA verification. (Tenants do not require this)."
    )
    
    # ✅ NEW: Flag to force password change on first login for manager-created tenants
    requires_password_change = models.BooleanField(
        'Requires Password Change',
        default=False,
        help_text="If True, the user will be forced to change their temporary password on next login."
    )
    
    is_active = models.BooleanField(
        'Active', 
        default=True, 
        help_text="Designates whether this user should be treated as active."
    )
    
    date_joined = models.DateTimeField('Date Joined', default=timezone.now)
    updated_at = models.DateTimeField('Last Updated', auto_now=True)

    objects = UserManager()

    # Tell Django to use email for authentication
    USERNAME_FIELD = 'email'
    # ✅ FIXED: Removed 'phone_number' because it is optional (null=True). 
    # Keeping it here would break the `createsuperuser` command.
    REQUIRED_FIELDS = ['role'] 

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role', 'is_verified']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    @property
    def is_landlord(self):
        return self.role == self.Role.LANDLORD

    @property
    def is_agency(self):
        return self.role == self.Role.AGENCY

    @property
    def is_tenant(self):
        return self.role == self.Role.TENANT