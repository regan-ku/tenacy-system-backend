import uuid
import hashlib
from django.db import models
from django.conf import settings
from .document import Document
from .document_template import DocumentTemplate

class GenerationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    GENERATED = "generated", "Generated"
    FAILED = "failed", "Failed"
    ARCHIVED = "archived", "Archived"

class GeneratedDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # 1:1 link to the master Document registry
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name="generated_record")
    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT, related_name="generated_instances")

    # Explicit nullable FKs to key system entities (avoids GenericForeignKey overhead)
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_documents")
    payment = models.ForeignKey("payments.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_documents")
    property_obj = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_documents")
    application = models.ForeignKey("applications.Application", on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_documents")

    # Generation metadata
    generation_variables = models.JSONField(default=dict, blank=True, help_text="Snapshot of variables injected into template")
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="documents_generated")
    status = models.CharField(max_length=20, choices=GenerationStatus.choices, default=GenerationStatus.PENDING, db_index=True)
    
    # Integrity & compliance fields
    checksum = models.CharField(max_length=64, blank=True, null=True, help_text="SHA-256 hash for tamper verification")
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    page_count = models.PositiveIntegerField(default=0, blank=True, null=True)

    class Meta:
        ordering = ["-generated_at"]
        verbose_name = "Generated Document"
        verbose_name_plural = "Generated Documents"
        indexes = [
            models.Index(fields=["status", "generated_at"]),
            models.Index(fields=["tenancy", "status"]),
            models.Index(fields=["payment", "status"]),
        ]

    def __str__(self):
        return f"{self.document.title} | {self.get_status_display()} | {self.generated_at.strftime('%Y-%m-%d')}"

    def compute_checksum(self, file_bytes: bytes) -> str:
        """Generates SHA-256 hash for post-generation integrity verification."""
        return hashlib.sha256(file_bytes).hexdigest()

    def get_source_entity(self):
        """Helper to return the actual entity this document belongs to."""
        return self.tenancy or self.payment or self.property_obj or self.application