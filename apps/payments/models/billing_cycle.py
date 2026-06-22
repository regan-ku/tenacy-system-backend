import uuid
from django.db import models

class CycleType(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    YEARLY = "yearly", "Yearly"

class BillingCycle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    cycle_type = models.CharField(max_length=20, choices=CycleType.choices)
    billing_day = models.PositiveIntegerField(help_text="Day of month (1-31) or day of week (0-6)")
    grace_period_days = models.PositiveIntegerField(default=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["name", "cycle_type"]
        ordering = ["cycle_type"]

    def __str__(self):
        return f"{self.name} | {self.get_cycle_type_display()}"