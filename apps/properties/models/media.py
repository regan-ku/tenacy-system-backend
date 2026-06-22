from django.db import models
from .property import Property
from .unit import Unit

class PropertyMedia(models.Model):
    """
    Handles additional images, videos, documents, and virtual tours for properties, unit groups, and units.
    (Primary cover photos are handled by the cover_photo field on Property/UnitGroup/Unit models).
    """
    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'
        VIRTUAL_TOUR = 'virtual_tour', 'Virtual Tour (360)'
        FLOOR_PLAN = 'floor_plan', 'Floor Plan'
        # ✅ NEW: Added DOCUMENT support for Title Deeds, KRA PINs, IDs, etc.
        DOCUMENT = 'document', 'Document (PDF/Deed/ID)'

    property_ref = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='media'
    )
    
    # ✅ NEW: Link media to a Unit Group (e.g., gallery photos for "2-Bedroom" units)
    unit_group = models.ForeignKey(
        'UnitGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='media',
        help_text="Optional: Link media to a specific unit group."
    )
    
    unit = models.ForeignKey(
        Unit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='media',
        help_text="Optional: Link media to a specific individual unit."
    )
    
    media_type = models.CharField('Media Type', max_length=20, choices=MediaType.choices, default=MediaType.IMAGE)
    file = models.FileField('Media File', upload_to='properties/media/%Y/%m/')
    url = models.URLField('External URL', blank=True, null=True, help_text="For external video links (e.g., YouTube, Vimeo)")
    
    caption = models.CharField('Caption', max_length=255, blank=True, null=True)
    display_order = models.PositiveIntegerField('Display Order', default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Property Media'
        verbose_name_plural = 'Property Media'
        ordering = ['property_ref', 'display_order']

    def __str__(self):
        return f"Media for {self.property_ref.title} ({self.get_media_type_display()})"