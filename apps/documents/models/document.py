import uuid
from django.db import models
from django.conf import settings
from .document_type import DocumentType
from .document_template import DocumentTemplate

class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_SIGNATURE = "pending_signature", "Pending Signature"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"
    EXPIRED = "expired", "Expired"
    REJECTED = "rejected", "Rejected"

class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name="documents")
    template = models.ForeignKey(DocumentTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_docs")
    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, null=True, blank=True, related_name="documents")
    unit = models.ForeignKey("properties.Unit", on_delete=models.CASCADE, null=True, blank=True, related_name="documents")
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.CASCADE, null=True, blank=True, related_name="documents")
    
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="uploaded_documents")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_documents", help_text="Tenant/agent who must review/sign")
    
    title = models.CharField(max_length=200)
    file_url = models.URLField(help_text="Secure cloud storage link")
    status = models.CharField(max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Source reference, generation params, etc.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "document_type"]),
            models.Index(fields=["tenancy", "status"]),
            models.Index(fields=["property", "unit"]),
        ]
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    def __str__(self):
        return f"{self.title} | {self.get_status_display()}"