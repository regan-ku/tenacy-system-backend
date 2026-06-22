import uuid
from decimal import Decimal
from django.db import models

class InvoiceStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    PARTIAL = "partial", "Partially Paid"
    OVERDUE = "overdue", "Overdue"
    VOID = "void", "Void"
    CANCELLED = "cancelled", "Cancelled"

class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.PROTECT, related_name="invoices")
    period_start = models.DateField()
    period_end = models.DateField()
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    balance_due = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_date", "-created_at"]
        indexes = [models.Index(fields=["tenancy", "status"])]

    def __str__(self):
        return f"INV-{self.invoice_number} | {self.tenancy} | {self.status}"