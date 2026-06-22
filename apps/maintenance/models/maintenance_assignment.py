import uuid
from django.db import models
from django.conf import settings
from .maintenance_request import MaintenanceRequest

class AssignmentRole(models.TextChoices):
    CARETAKER = "caretaker", "Caretaker"
    AGENT = "agent", "Agent"
    TECHNICIAN = "technician", "External Technician"

class AssignmentStatus(models.TextChoices):
    PENDING = "pending", "Pending Acknowledgment"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    REASSIGNED = "reassigned", "Reassigned"

class MaintenanceAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="assignment_history")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="maintenance_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="maintenance_assignments_made")
    role_type = models.CharField(max_length=20, choices=AssignmentRole.choices)
    status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.PENDING)
    assigned_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Maintenance Assignment"
        verbose_name_plural = "Maintenance Assignments"

    def __str__(self):
        return f"Assignment | {self.request.id[:8]} → {self.assigned_to.email} | {self.get_status_display()}"