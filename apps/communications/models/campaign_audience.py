import uuid
from django.db import models
from .campaign import Campaign

class AudienceType(models.TextChoices):
    ROLE = "role", "By User Role"
    PROPERTY_TENANTS = "property_tenants", "Tenants of Specific Properties"
    ARREARS_LIST = "arrears_list", "Users with Overdue Balances"
    CUSTOM_LIST = "custom_list", "Custom User IDs"
    SYSTEM_WIDE = "system_wide", "All Active Users"

class CampaignAudience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="audiences")
    audience_type = models.CharField(max_length=20, choices=AudienceType.choices)
    filter_criteria = models.JSONField(default=dict, help_text="Role, property IDs, or custom user list")
    estimated_count = models.PositiveIntegerField(default=0)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Campaign Audiences"

    def __str__(self):
        return f"{self.campaign.title} → {self.get_audience_type_display()}"