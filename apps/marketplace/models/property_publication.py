from django.db import models
from django.conf import settings
from django.utils import timezone

class PropertyPublication(models.Model):
    class VisibilityStatus(models.TextChoices):
        VISIBLE = 'visible', 'Visible on Marketplace'
        HIDDEN = 'hidden', 'Hidden (Internal Only)'
        UNPUBLISHED = 'unpublished', 'Unpublished'
        SUSPENDED = 'suspended', 'Suspended by Admin'

    property = models.OneToOneField(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='publication',
        help_text="The property being published."
    )

    is_published = models.BooleanField('Is Published', default=False)
    published_at = models.DateTimeField('Published At', blank=True, null=True)
    unpublished_at = models.DateTimeField('Unpublished At', blank=True, null=True)
    
    visibility_status = models.CharField(
        'Visibility Status',
        max_length=20,
        choices=VisibilityStatus.choices,
        default=VisibilityStatus.UNPUBLISHED
    )

    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_properties'
    )
    
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_publications'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Property Publication'
        verbose_name_plural = 'Property Publications'
        indexes = [
            models.Index(fields=['is_published', 'visibility_status']),
        ]

    def __str__(self):
        status = "Published" if self.is_published else "Unpublished"
        return f"{self.property.title} - {status}"

    def save(self, *args, **kwargs):
        # ✅ CRITICAL FIX: Auto-sync visibility_status when is_published changes.
        # This ensures the Django Admin checkbox actually triggers marketplace visibility.
        if self.pk:
            try:
                previous = PropertyPublication.objects.get(pk=self.pk)
                prev_published = previous.is_published
            except PropertyPublication.DoesNotExist:
                prev_published = False
        else:
            prev_published = False

        if self.is_published and not prev_published:
            self.visibility_status = self.VisibilityStatus.VISIBLE
            self.published_at = timezone.now()
            self.unpublished_at = None
        elif not self.is_published and prev_published:
            if self.visibility_status == self.VisibilityStatus.VISIBLE:
                self.visibility_status = self.VisibilityStatus.HIDDEN
            self.unpublished_at = timezone.now()

        super().save(*args, **kwargs)

    def publish(self, user):
        self.is_published = True
        self.visibility_status = self.VisibilityStatus.VISIBLE
        self.published_at = timezone.now()
        self.published_by = user
        self.last_modified_by = user
        self.save()

    def hide(self, user):
        self.visibility_status = self.VisibilityStatus.HIDDEN
        self.last_modified_by = user
        self.save()