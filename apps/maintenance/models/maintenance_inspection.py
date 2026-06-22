import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class InspectionStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"

class MaintenanceInspection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="inspections")
    unit = models.ForeignKey("properties.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections")
    inspector = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conducted_inspections")
    inspection_date = models.DateField()
    findings = models.TextField(blank=True, help_text="Condition report notes")
    status = models.CharField(max_length=20, choices=InspectionStatus.choices, default=InspectionStatus.SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inspection_date"]
        verbose_name = "Maintenance Inspection"
        verbose_name_plural = "Maintenance Inspections"

    def save(self, *args, **kwargs):
        # Auto-flag overdue inspections
        if self.inspection_date < timezone.now().date() and self.status == InspectionStatus.SCHEDULED:
            self.status = InspectionStatus.OVERDUE
        super().save(*args, **kwargs)

    def __str__(self):
        unit_code = self.unit.unit_code if self.unit else "General Property"
        return f"Inspection | {self.property.title} ({unit_code}) | {self.inspection_date} | {self.get_status_display()}"