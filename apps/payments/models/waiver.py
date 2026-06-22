import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings

class Waiver(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenancy = models.ForeignKey(
        "tenancy.Tenancy", 
        on_delete=models.PROTECT, 
        related_name="payment_waivers"  # ✅ UNIQUE to avoid clash
    )
    invoice = models.ForeignKey("Invoice", on_delete=models.SET_NULL, null=True, related_name="financial_waivers")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Financial Waiver | {self.tenancy} | {self.amount}"