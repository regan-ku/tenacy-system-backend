from django.core.exceptions import ValidationError
from ..models import PaymentAccount

class AccountValidationService:
    @staticmethod
    def validate_for_collection(account_id: str) -> PaymentAccount:
        """
        Strict validation before initiating any STK/C2B request.
        Prevents routing to unverified, suspended, or test accounts.
        """
        try:
            account = PaymentAccount.objects.select_related("owner").get(id=account_id)
        except PaymentAccount.DoesNotExist:
            raise ValidationError("Payment routing account not found.")

        if not account.is_verified:
            raise ValidationError("Account is not verified. Complete verification before collecting funds.")
        if not account.is_active:
            raise ValidationError("Account is inactive. Please activate routing account.")
        if account.verification_status == "rejected":
            raise ValidationError("Account verification was rejected.")

        return account