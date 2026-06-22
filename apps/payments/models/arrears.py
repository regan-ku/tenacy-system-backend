import uuid
from decimal import Decimal
from django.db import models

class ArrearsStatus(models.TextChoices):
    CURRENT = "current", "Current"
    OVERDUE = "overdue", "Overdue"
    ESCALATED = "escalated", "Escalated"

class Arrears(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenancy = models.OneToOneField("tenancy.Tenancy", on_delete=models.PROTECT, related_name="arrears_record")
    total_outstanding = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    oldest_overdue_date = models.DateField(null=True, blank=True)
    days_overdue = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=ArrearsStatus.choices, default=ArrearsStatus.CURRENT, db_index=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-total_outstanding"]

    def __str__(self):
        return f"Arrears | {self.tenancy} | {self.total_outstanding}"