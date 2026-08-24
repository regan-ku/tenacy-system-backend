from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import PaymentAccount, PaymentAccountVerification


class PaymentVerificationService:
    """
    PLATFORM SETTLEMENT MODEL
    -------------------------
    Manages the verification lifecycle for settlement/payout accounts.
    
    The PaymentAccountVerification model's save() method auto-syncs
    is_verified and verification_status to the parent PaymentAccount.
    This service additionally handles is_active toggling.
    """

    @staticmethod
    @transaction.atomic
    def initiate_verification(account_id, user_id, method="manual_review", reference=None):
        """
        Starts the verification process for a settlement account.
        Supersedes any existing pending verifications for this account.
        """
        try:
            account = PaymentAccount.objects.get(id=account_id, owner_id=user_id)
        except PaymentAccount.DoesNotExist:
            raise ValidationError("Payment account not found or you do not own it.")

        # Supersede any pending verifications for this account
        # Using .update() here is intentional - we don't want to trigger
        # the model's save() sync logic for cancelled records
        PaymentAccountVerification.objects.filter(
            payment_account=account,
            status="pending"
        ).update(status="rejected", notes="Superseded by new verification request")

        verification = PaymentAccountVerification.objects.create(
            payment_account=account,
            requested_by_id=user_id,
            method=method,
            status="pending",
            reference=reference
        )
        return verification

    @staticmethod
    @transaction.atomic
    def approve_verification(verification_id, verified_by_user, notes=""):
        """
        Marks account as verified & activates it automatically.
        
        The model's save() method handles syncing is_verified and
        verification_status to the parent account. This method
        additionally activates the account for payouts.
        """
        try:
            verification = PaymentAccountVerification.objects.select_related(
                "payment_account"
            ).get(id=verification_id)
        except PaymentAccountVerification.DoesNotExist:
            raise ValidationError("Verification record not found.")

        if verification.status != "pending":
            raise ValidationError("Verification is not in pending state.")

        verification.status = "verified"
        verification.verified_by = verified_by_user
        verification.notes = notes
        verification.verified_at = timezone.now()
        verification.save()  # Triggers model's save() sync to parent

        # ✅ Activate the account for payouts
        # (model's save() handles is_verified + verification_status,
        #  but is_active must be set here)
        account = verification.payment_account
        if not account.is_active:
            account.is_active = True
            account.save(update_fields=["is_active"])

        return {"status": "verified", "account_id": str(account.id)}

    @staticmethod
    @transaction.atomic
    def reject_verification(verification_id, verified_by_user, notes=""):
        """
        Rejects verification request. Account remains inactive.
        
        The model's save() method handles syncing is_verified=False and
        verification_status="rejected" to the parent account.
        """
        try:
            verification = PaymentAccountVerification.objects.select_related(
                "payment_account"
            ).get(id=verification_id)
        except PaymentAccountVerification.DoesNotExist:
            raise ValidationError("Verification record not found.")

        if verification.status != "pending":
            raise ValidationError("Verification is not in pending state.")

        verification.status = "rejected"
        verification.verified_by = verified_by_user
        verification.notes = notes
        verification.verified_at = timezone.now()
        verification.save()  # Triggers model's save() sync to parent

        # ✅ Ensure account is deactivated on rejection
        account = verification.payment_account
        if account.is_active:
            account.is_active = False
            account.save(update_fields=["is_active"])

        return {"status": "rejected", "account_id": str(account.id)}

    @staticmethod
    @transaction.atomic
    def suspend_verification(verification_id, verified_by_user, notes=""):
        """
        Suspends a previously verified account.
        Used for fraud prevention or compliance issues.
        """
        try:
            verification = PaymentAccountVerification.objects.select_related(
                "payment_account"
            ).get(id=verification_id)
        except PaymentAccountVerification.DoesNotExist:
            raise ValidationError("Verification record not found.")

        verification.status = "suspended"
        verification.verified_by = verified_by_user
        verification.notes = notes
        verification.save()  # Triggers model's save() sync to parent

        # ✅ Deactivate account on suspension
        account = verification.payment_account
        account.is_active = False
        account.verification_status = "suspended"
        account.save(update_fields=["is_active", "verification_status"])

        return {"status": "suspended", "account_id": str(account.id)}

    @staticmethod
    def is_account_verified_and_active(account_id):
        """Quick gate check used by payout routing & B2C handlers."""
        return PaymentAccount.objects.filter(
            id=account_id,
            is_active=True,
            is_verified=True
        ).exists()