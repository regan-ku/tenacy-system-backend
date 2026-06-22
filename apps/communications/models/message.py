import uuid
from django.db import models
from django.conf import settings
from .message_template import Channel

class MessageType(models.TextChoices):
    SYSTEM = "system", "System"
    TRANSACTIONAL = "transactional", "Transactional"
    ALERT = "alert", "Alert"
    REMINDER = "reminder", "Reminder"
    CAMPAIGN = "campaign", "Campaign"

class MessageStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    READ = "read", "Read"

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outbound_messages")
    channel = models.CharField(max_length=20, choices=Channel.choices)
    message_type = models.CharField(max_length=20, choices=MessageType.choices)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=MessageStatus.choices, default=MessageStatus.QUEUED, db_index=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Template ID, campaign ID, or routing info")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "status"]), 
            models.Index(fields=["channel", "created_at"])
        ]

    def __str__(self):
        return f"{self.get_channel_display()} → {self.recipient.email} | {self.get_status_display()}"