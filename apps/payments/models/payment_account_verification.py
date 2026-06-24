import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class VerificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"

class PaymentAccountVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_account = models.ForeignKey(
        "PaymentAccount", 
        on_delete=models.CASCADE, 
        related_name="verifications"
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    method = models.CharField(max_length=50, help_text="e.g., mpesa_b2c_test, manual_review")
    status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING, db_index=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Verification for {self.payment_account.account_name} | {self.status}"

    # ✅ THE FIX: Auto-sync to PaymentAccount whenever this model is saved
    def save(self, *args, **kwargs):
        # Check if this is an update (object already exists in DB)
        is_updating = self.pk is not None
        
        if is_updating:
            account = self.payment_account
            
            # 1. If status becomes VERIFIED, sync the parent account
            if self.status == VerificationStatus.VERIFIED:
                if not account.is_verified or account.verification_status != VerificationStatus.VERIFIED:
                    account.is_verified = True
                    account.verification_status = VerificationStatus.VERIFIED
                    account.verified_at = self.verified_at or timezone.now()
                    # Save only the changed fields to avoid triggering unnecessary signals
                    account.save(update_fields=['is_verified', 'verification_status', 'verified_at'])

            # 2. If status becomes REJECTED, sync the parent account status
            elif self.status == VerificationStatus.REJECTED:
                if account.verification_status != VerificationStatus.REJECTED:
                    account.verification_status = VerificationStatus.REJECTED
                    account.is_verified = False
                    account.save(update_fields=['is_verified', 'verification_status'])

        # Finally, save the Verification record itself
        super().save(*args, **kwargs)