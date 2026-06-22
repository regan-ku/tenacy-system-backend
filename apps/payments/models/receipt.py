import uuid
from django.db import models

from ..models.payment import Payment

class Receipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True, db_index=True)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="receipts")
    tenancy = models.ForeignKey("tenancy.Tenancy", on_delete=models.PROTECT, related_name="receipts")
    file_url = models.URLField(blank=True, null=True, help_text="Link to generated PDF")
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Receipt {self.receipt_number} | {self.tenancy}"