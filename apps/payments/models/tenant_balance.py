import uuid
from decimal import Decimal
from django.db import models

class TenantBalance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenancy = models.OneToOneField("tenancy.Tenancy", on_delete=models.PROTECT, related_name="balance_record")
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_invoiced = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_updated"]

    def __str__(self):
        return f"Balance | {self.tenancy} | {self.current_balance}"