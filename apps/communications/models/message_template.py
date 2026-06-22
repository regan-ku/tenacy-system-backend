import uuid
from django.db import models

class Channel(models.TextChoices):
    SMS = "sms", "SMS"
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    IN_APP = "in_app", "In-App"

class MessageTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    subject = models.CharField(max_length=255, blank=True, null=True, help_text="Email subject line")
    body = models.TextField(help_text="Use {variable} placeholders for dynamic content")
    required_variables = models.JSONField(default=list, help_text="List of expected placeholders")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_channel_display()})"