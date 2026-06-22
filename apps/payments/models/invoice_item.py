import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

class ItemType(models.TextChoices):
    RENT = "rent", "Base Rent"
    SERVICE_CHARGE = "service_charge", "Service Charge"
    UTILITIES = "utilities", "Utilities (Water/Electricity)"
    LATE_FEE = "late_fee", "Late Penalty"
    DEPOSIT = "deposit", "Security/Utility Deposit"
    MAINTENANCE = "maintenance", "Maintenance Fee"
    ADJUSTMENT = "adjustment", "Manual Adjustment/Credit"
    OTHER = "other", "Other"

class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey("Invoice", on_delete=models.CASCADE, related_name="line_items")
    item_type = models.CharField(max_length=30, choices=ItemType.choices, db_index=True)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    quantity = models.PositiveIntegerField(default=1, help_text="For metered utilities or multi-unit charges")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Auto-filled if quantity > 1")
    is_taxable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item_type", "description"]
        verbose_name_plural = "Invoice Items"

    def __str__(self):
        return f"{self.get_item_type_display()} | {self.amount} | INV {self.invoice.invoice_number}"

    @property
    def subtotal(self):
        """Calculates extended amount for billing engines"""
        return self.amount * self.quantity