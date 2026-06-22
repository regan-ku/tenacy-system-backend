import uuid
from django.db import models
from django.conf import settings
from .maintenance_request import MaintenanceRequest

class EventType(models.TextChoices):
    CREATED = "created", "Created"
    STATUS_CHANGED = "status_changed", "Status Changed"
    ASSIGNED = "assigned", "Assigned"
    MEDIA_UPLOADED = "media_uploaded", "Media Uploaded"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    SLA_BREACH = "sla_breach", "SLA Breach"
    REASSIGNED = "reassigned", "Reassigned"

class MaintenanceHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="audit_history")
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    previous_value = models.JSONField(blank=True, null=True, help_text="Snapshot before change")
    new_value = models.JSONField(blank=True, null=True, help_text="Snapshot after change")
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["request", "event_type"])]
        verbose_name = "Maintenance Audit History"
        verbose_name_plural = "Maintenance Audit Histories"

    def __str__(self):
        return f"History | {self.request.id[:8]} | {self.get_event_type_display()} | {self.created_at.strftime('%Y-%m-%d %H:%M')}"