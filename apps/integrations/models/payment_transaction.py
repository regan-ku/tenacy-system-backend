import uuid
from django.db import models
from django.conf import settings

class PaymentTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, related_name="payment_transactions"
    )
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default="initiated", db_index=True)
    reference = models.CharField(max_length=255, blank=True, null=True, help_text="Invoice/Tenancy reference")
    provider_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.transaction_id} | {self.amount} {self.currency} | {self.status}"