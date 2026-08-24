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
    PENDING_RECONCILIATION = "pending_reconciliation", "Pending Reconciliation" # ✅ Added for manual payments

class PaymentSource(models.TextChoices):
    MPESA = "mpesa", "M-Pesa"
    BANK = "bank", "Bank Transfer"
    CASH = "cash", "Cash"
    OTHER = "other", "Other"

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ✅ CRITICAL FOR PLATFORM MODEL: Explicitly link to the tenancy this payment is for
    tenancy = models.ForeignKey(
        "tenancy.Tenancy", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="payments",
        help_text="The tenancy this payment is intended for (crucial for future credits/arrears)"
    )
    
    payment_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="External Transaction Code (e.g., QJ...7H)")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="payments_made")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=20, choices=PaymentSource.choices)
    status = models.CharField(max_length=30, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True)
    
    # ✅ CRITICAL FOR PLATFORM MODEL: Store the reference the tenant typed in their M-Pesa app
    account_reference = models.CharField(
        max_length=50, 
        blank=True, 
        db_index=True, 
        help_text="The Account Reference used in the STK push (e.g., TEN-12345678 or INV-999)"
    )
    
    account_received_at = models.CharField(max_length=100, help_text="Phone/Paybill that received the funds (Platform Paybill)")
    raw_payload = models.JSONField(default=dict, blank=True, help_text="Provider callback data")
    
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-created_at"]
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"{self.payment_id} | {self.amount} | {self.status}"