import uuid
from django.db import models

class MaintenanceCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True, db_index=True, help_text="e.g., plumbing, electrical, structural")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    default_sla_hours = models.PositiveIntegerField(default=72, help_text="Default resolution SLA in hours")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Maintenance Category"
        verbose_name_plural = "Maintenance Categories"

    def __str__(self):
        return f"{self.name} (SLA: {self.default_sla_hours}h)"