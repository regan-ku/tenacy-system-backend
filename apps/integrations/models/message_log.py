import uuid
from django.db import models
from django.conf import settings

class Channel(models.TextChoices):
    SMS = "sms", "SMS"
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    IN_APP = "in_app", "In-App"

class MessageLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="message_logs"
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    message_content = models.TextField()
    message_type = models.CharField(max_length=30, default="transactional")
    status = models.CharField(max_length=20, default="queued", db_index=True)
    external_ref = models.CharField(max_length=100, blank=True, null=True, help_text="Provider message ID")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["channel", "created_at"]),
        ]

    def __str__(self):
        return f"{self.channel.upper()} → {self.recipient.email} | {self.status}"