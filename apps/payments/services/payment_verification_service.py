from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import PaymentAccount, PaymentAccountVerification

class PaymentVerificationService:
    @staticmethod
    @transaction.atomic
    def initiate_verification(account_id, user_id, method="manual_review", reference=None):
        """Starts verification process for a payment account."""
        account = PaymentAccount.objects.get(id=account_id, owner_id=user_id)
        
        # Cancel any pending verifications for this account
        PaymentAccountVerification.objects.filter(
            payment_account=account, 
            verification_status="pending"
        ).update(verification_status="cancelled")

        verification = PaymentAccountVerification.objects.create(
            payment_account=account,
            verification_method=method,
            verification_status="pending",
            verification_reference=reference
        )
        return verification

    @staticmethod
    @transaction.atomic
    def approve_verification(verification_id, verified_by_user, notes=""):
        """Marks account as verified & activates it automatically."""
        verification = PaymentAccountVerification.objects.select_related("payment_account").get(id=verification_id)
        if verification.verification_status != "pending":
            raise ValidationError("Verification is not in pending state.")

        verification.verification_status = "verified"
        verification.verified_by = verified_by_user
        verification.verification_notes = notes
        verification.verification_timestamp = timezone.now()
        verification.save()

        # Activate parent account
        account = verification.payment_account
        account.is_verified = True
        account.is_active = True
        account.verification_status = "verified"
        account.verified_at = timezone.now()
        account.save(update_fields=["is_verified", "is_active", "verification_status", "verified_at"])
        
        return {"status": "verified", "account_id": str(account.id)}

    @staticmethod
    @transaction.atomic
    def reject_verification(verification_id, verified_by_user, notes=""):
        """Rejects verification request. Account remains inactive."""
        verification = PaymentAccountVerification.objects.select_related("payment_account").get(id=verification_id)
        if verification.verification_status != "pending":
            raise ValidationError("Verification is not in pending state.")

        verification.verification_status = "rejected"
        verification.verified_by = verified_by_user
        verification.verification_notes = notes
        verification.verification_timestamp = timezone.now()
        verification.save(update_fields=["verification_status", "verified_by", "verification_notes", "verification_timestamp"])

        return {"status": "rejected", "account_id": str(verification.payment_account.id)}

    @staticmethod
    def is_account_verified_and_active(account_id):
        """Quick gate check used by payment routing & callback handlers."""
        return PaymentAccount.objects.filter(id=account_id, is_active=True, is_verified=True).exists()