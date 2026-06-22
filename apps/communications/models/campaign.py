import uuid
from django.db import models
from django.conf import settings
from .message_template import Channel, MessageTemplate

class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"

class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="created_comm_campaigns"  # ✅ UNIQUE to avoid integrations.Campaign clash
    )
    title = models.CharField(max_length=200)
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT, related_name="used_in_campaigns")
    channel = models.CharField(max_length=20, choices=Channel.choices)
    status = models.CharField(
        max_length=20, 
        choices=CampaignStatus.choices, 
        default=CampaignStatus.DRAFT, 
        db_index=True
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict, help_text="Delivery rates, open rates, failures")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "channel"])]
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"

    def __str__(self):
        return f"{self.title} | {self.get_status_display()}"