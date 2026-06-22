import uuid
from django.db import models
from django.conf import settings

class Provider(models.TextChoices):
    MPESA = "mpesa", "M-Pesa"
    AFRICASTALKING = "africastalking", "Africa's Talking"
    WHATSAPP = "whatsapp", "WhatsApp Business"
    EMAIL = "email", "Email Service"

class IntegrationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=30, choices=Provider.choices, db_index=True)
    endpoint = models.CharField(max_length=255)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending", db_index=True)
    retry_count = models.PositiveIntegerField(default=0)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, related_name="integration_logs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.provider.upper()} | {self.status} | {self.created_at.strftime('%Y-%m-%d %H:%M')}"