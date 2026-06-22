import uuid
from django.db import models
from .document_type import DocumentType

class DocumentTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name="templates")
    name = models.CharField(max_length=100)
    template_content = models.TextField(help_text="HTML/Jinja template content or raw text with {placeholders}")
    variables = models.JSONField(default=list, help_text="Expected dynamic variables like ['tenant_name', 'rent_amount']")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name = "Document Template"
        verbose_name_plural = "Document Templates"

    def __str__(self):
        return f"{self.name} | {self.document_type.code}"