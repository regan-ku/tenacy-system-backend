import uuid
from django.db import models
from django.conf import settings
from .maintenance_category import MaintenanceCategory

class RequestStatus(models.TextChoices):
    OPEN = "open", "Open"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In Progress"
    PENDING_REVIEW = "pending_review", "Pending Review"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"

class RequestPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    EMERGENCY = "emergency", "Emergency"

class MaintenanceRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey("properties.Property", on_delete=models.PROTECT, related_name="maintenance_requests")
    unit = models.ForeignKey("properties.Unit", on_delete=models.PROTECT, related_name="maintenance_requests", help_text="Every request must be tied to a unit")
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_requests", help_text="Nullable: caretakers can report in vacant units")
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_maintenance_requests")
    category = models.ForeignKey(MaintenanceCategory, on_delete=models.PROTECT, related_name="requests")
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=RequestPriority.choices, default=RequestPriority.MEDIUM, db_index=True)
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.OPEN, db_index=True)
    
    sla_due_at = models.DateTimeField(null=True, blank=True, help_text="Auto-calculated based on category SLA + priority multiplier")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="assigned_maintenance_tasks", help_text="Primary responder (caretaker/agent/technician)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["property", "unit"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["sla_due_at", "status"])
        ]
        verbose_name = "Maintenance Request"
        verbose_name_plural = "Maintenance Requests"

    def __str__(self):
        return f"{self.title} | {self.unit.unit_code if self.unit else 'N/A'} | {self.get_status_display()}"