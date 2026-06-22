import uuid
from django.db import models
from django.conf import settings
from .document import Document

class DocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    file_url = models.URLField()
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    change_reason = models.TextField(blank=True, null=True, help_text="Why this version was created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        verbose_name = "Document Version"
        verbose_name_plural = "Document Versions"

    def __str__(self):
        return f"v{self.version_number} | {self.document.title}"