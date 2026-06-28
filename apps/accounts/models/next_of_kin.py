from django.db import models
from django.conf import settings
from ..utils.validators import validate_phone_number

class NextOfKin(models.Model):
    """
    Emergency contact information for users.
    Crucial for tenant safety, property management protocols, and application reviews.
    """
    RELATIONSHIP_CHOICES = [
        ('spouse', 'Spouse'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
        ('child', 'Child'),
        ('relative', 'Relative'),
        ('friend', 'Friend'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='next_of_kin_contacts',
        help_text="The user this emergency contact belongs to."
    )
    
    full_name = models.CharField('Full Name', max_length=255)
    relationship = models.CharField('Relationship', max_length=20, choices=RELATIONSHIP_CHOICES)
    
    phone_number = models.CharField(
        'Phone Number', 
        max_length=15, 
        validators=[validate_phone_number],
        help_text="Format: +254712345678 or 0712345678"
    )
    
    city = models.CharField('City of Residence', max_length=100, blank=True, null=True)
    is_primary = models.BooleanField('Primary Contact', default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Next of Kin'
        verbose_name_plural = 'Next of Kin Contacts'
        indexes = [
            models.Index(fields=['user', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()}) for {self.user.email}"

    def save(self, *args, **kwargs):
        """
        Ensure only ONE primary contact exists per user.
        """
        if self.is_primary:
            NextOfKin.objects.filter(user=self.user, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)