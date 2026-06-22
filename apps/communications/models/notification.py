import uuid
from django.db import models
from django.conf import settings

class NotificationType(models.TextChoices):
    SYSTEM = "system", "System"
    TRANSACTIONAL = "transactional", "Transactional"
    ALERT = "alert", "Alert"
    REMINDER = "reminder", "Reminder"
    CAMPAIGN = "campaign", "Campaign"

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    is_read = models.BooleanField(default=False, db_index=True)
    action_link = models.CharField(max_length=255, blank=True, null=True, help_text="Frontend route to navigate")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.title} → {self.user.email} ({'Read' if self.is_read else 'Unread'})"