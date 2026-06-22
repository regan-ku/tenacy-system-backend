import uuid
from django.db import models

class WebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=50, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "processed"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        status_icon = "✅" if self.processed else "⏳"
        return f"{self.source} | {self.event_type} | {status_icon}"