import uuid
from django.db import models
from django.conf import settings
from .document import Document

class AuditAction(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    VIEWED = "viewed", "Viewed"
    DOWNLOADED = "downloaded", "Downloaded"
    SIGNED = "signed", "Signed"
    REJECTED = "rejected", "Rejected"
    ARCHIVED = "archived", "Archived"
    VERSION_CREATED = "version_created", "Version Created"

class DocumentAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="audit_trail")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=AuditAction.choices)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Signature hash, download timestamp, etc.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["document", "action"])]
        verbose_name = "Document Audit Log"
        verbose_name_plural = "Document Audit Logs"

    def __str__(self):
        actor = self.user.email if self.user else "System"
        return f"{self.document.title} | {self.get_action_display()} | {actor}"