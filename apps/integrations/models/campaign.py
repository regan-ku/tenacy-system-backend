import uuid
from django.db import models
from django.conf import settings

class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"

class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, related_name="created_campaigns"
    )
    title = models.CharField(max_length=200)
    message_template = models.TextField(help_text="Template with placeholders like {first_name}")
    channel = models.CharField(max_length=20, choices=[
        ("sms", "SMS"), ("whatsapp", "WhatsApp"), ("email", "Email")
    ])
    target_audience = models.JSONField(default=dict, help_text="Filters/IDs for audience selection")
    status = models.CharField(max_length=20, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "channel"])]

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"