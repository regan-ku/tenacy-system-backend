import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings

class RefundStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    APPROVED = "approved", "Approved"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"

class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="refund_requests")
    processed_at = models.DateTimeField(null=True, blank=True)
    transaction_ref = models.CharField(max_length=100, blank=True, null=True, help_text="M-Pesa B2C Ref")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund | {self.tenancy} | {self.amount} | {self.status}"