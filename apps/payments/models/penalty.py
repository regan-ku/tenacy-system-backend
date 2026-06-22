import uuid
from decimal import Decimal
from django.db import models

class PenaltyType(models.TextChoices):
    LATE_FEE = "late_fee", "Late Fee"
    INSUFFICIENT_FUNDS = "insufficient_funds", "Insufficient Funds Fee"
    BREACH = "breach", "Contract Breach Penalty"

class Penalty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.PROTECT, related_name="penalties")
    penalty_type = models.CharField(max_length=30, choices=PenaltyType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self):
        return f"Penalty | {self.get_penalty_type_display()} | {self.amount}"