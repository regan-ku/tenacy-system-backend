import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings

class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"
    RECONCILED = "reconciled", "Reconciled"

class PaymentSource(models.TextChoices):
    MPESA = "mpesa", "M-Pesa"
    BANK = "bank", "Bank Transfer"
    CASH = "cash", "Cash"
    OTHER = "other", "Other"

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="External Transaction Code (e.g., QJ...7H)")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="payments_made")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=20, choices=PaymentSource.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True)
    account_received_at = models.CharField(max_length=100, help_text="Phone/Paybill that received the funds")
    raw_payload = models.JSONField(default=dict, blank=True, help_text="Provider callback data")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.payment_id} | {self.amount} | {self.status}"