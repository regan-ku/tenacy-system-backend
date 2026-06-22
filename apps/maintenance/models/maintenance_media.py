import uuid
from django.db import models
from django.conf import settings
from .maintenance_request import MaintenanceRequest

class MediaType(models.TextChoices):
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"
    DOCUMENT = "document", "Document"

class MaintenanceMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="media_attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    media_type = models.CharField(max_length=20, choices=MediaType.choices)
    file_url = models.URLField(help_text="Cloud storage path (S3/Spaces)")
    caption = models.CharField(max_length=200, blank=True)
    is_before_after = models.BooleanField(default=False, help_text="True = proof of resolution/completion")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Maintenance Media"
        verbose_name_plural = "Maintenance Media Attachments"

    def __str__(self):
        return f"Media | {self.request.id[:8]} | {self.media_type} | {'Before/After' if self.is_before_after else 'Evidence'}"