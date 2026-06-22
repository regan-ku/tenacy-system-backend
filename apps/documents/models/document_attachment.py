import uuid
from django.db import models
from django.conf import settings
from .document import Document

class DocumentAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    file_url = models.URLField()
    file_type = models.CharField(max_length=20, help_text="e.g., pdf, image, scan")
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Attachment"
        verbose_name_plural = "Document Attachments"

    def __str__(self):
        return f"Attachment | {self.document.title} | {self.file_type}"