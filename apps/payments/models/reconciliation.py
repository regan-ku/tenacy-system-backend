import uuid
from django.db import models

from ..models.invoice import Invoice
from ..models.payment import Payment

class ReconciliationStatus(models.TextChoices):
    MATCHED = "matched", "Matched"
    MISMATCH = "mismatch", "Mismatch"
    UNALLOCATED = "unallocated", "Unallocated"

class Reconciliation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="reconciliation_records")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=ReconciliationStatus.choices, default=ReconciliationStatus.UNALLOCATED, db_index=True)
    discrepancy_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    reconciled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reconciled_at"]

    def __str__(self):
        return f"{self.payment.payment_id} ↔ {self.invoice.invoice_number if self.invoice else 'No Invoice'} | {self.status}"