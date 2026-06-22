import uuid
from django.db import models
from django.conf import settings
from .maintenance_request import MaintenanceRequest

class MaintenanceUpdate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="updates")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    comment = models.TextField()
    previous_status = models.CharField(max_length=20, blank=True, null=True)
    new_status = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Maintenance Update"
        verbose_name_plural = "Maintenance Updates"

    def __str__(self):
        author = self.updated_by.email if self.updated_by else "System"
        return f"Update | {self.request.id[:8]} | {author} | {self.created_at.strftime('%Y-%m-%d %H:%M')}"