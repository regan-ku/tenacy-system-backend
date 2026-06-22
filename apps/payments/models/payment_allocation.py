import uuid
from decimal import Decimal
from django.db import models

from ..models.invoice import Invoice
from ..models.payment import Payment

class AllocationType(models.TextChoices):
    INVOICE = "invoice", "Direct to Invoice"
    ARREARS = "arrears", "To Overdue Balance"
    FUTURE = "future", "Credit to Future Rent"

class PaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, related_name="payment_allocations")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    allocation_type = models.CharField(max_length=20, choices=AllocationType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Payment Allocations"

    def __str__(self):
        return f"{self.payment.payment_id} → {self.allocation_type} | {self.amount}"