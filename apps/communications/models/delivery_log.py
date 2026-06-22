import uuid
from django.db import models
from .message import Message

class DeliveryLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="delivery_attempts")
    provider = models.CharField(max_length=50, help_text="e.g., africastalking, whatsapp_api, smtp")
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default="pending")
    response_code = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    raw_response = models.JSONField(default=dict, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attempted_at"]
        verbose_name_plural = "Delivery Logs"

    def __str__(self):
        return f"Attempt {self.attempt_number} | Message {str(self.message.id)[:8]} | {self.status}"