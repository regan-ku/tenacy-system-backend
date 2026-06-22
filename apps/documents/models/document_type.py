import uuid
from django.db import models

class DocumentType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="e.g., LEASE, RECEIPT, ID, INSPECTION")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    requires_signature = models.BooleanField(default=False, help_text="Triggers signing workflow if True")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Document Type"
        verbose_name_plural = "Document Types"

    def __str__(self):
        return f"{self.name} ({self.code})"