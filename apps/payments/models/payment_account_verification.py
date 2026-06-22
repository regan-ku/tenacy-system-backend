import uuid
from django.db import models
from django.conf import settings

class VerificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"

class PaymentAccountVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    method = models.CharField(max_length=50, help_text="e.g., mpesa_b2c_test, manual_review")
    status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING, db_index=True)
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="Mpesa transaction ID for test deposit")
    notes = models.TextField(blank=True, null=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Verification | {self.method} | {self.status}"