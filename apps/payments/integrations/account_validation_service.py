from django.core.exceptions import ValidationError
from ..models import PaymentAccount

class AccountValidationService:
    @staticmethod
    def validate_for_payout(account_id: str) -> PaymentAccount:
        """
        PLATFORM SETTLEMENT MODEL:
        Strict validation before initiating any B2C payout or bank transfer 
        to a landlord/agency settlement account.
        Prevents routing platform funds to unverified, suspended, or inactive accounts.
        """
        try:
            account = PaymentAccount.objects.select_related("owner").get(id=account_id)
        except PaymentAccount.DoesNotExist:
            raise ValidationError("Settlement account not found.")

        if not account.is_verified:
            raise ValidationError("Settlement account is not verified. Cannot disburse funds.")
        if not account.is_active:
            raise ValidationError("Settlement account is inactive. Please activate it first.")
        if account.verification_status == "rejected":
            raise ValidationError("Settlement account verification was rejected.")
        if account.verification_status == "suspended":
            raise ValidationError("Settlement account is currently suspended for compliance review.")

        return account
        
    # Kept for backward compatibility if any old code references it
    validate_for_collection = validate_for_payout 