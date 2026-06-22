import re
from django.core.exceptions import ValidationError
from ..models import PaymentTransaction

class TransactionValidator:
    @staticmethod
    def validate_phone(phone: str) -> str:
        cleaned = re.sub(r"\D", "", phone)
        if cleaned.startswith("0"):
            cleaned = "254" + cleaned[1:]
        if not re.match(r"^254\d{9}$", cleaned):
            raise ValidationError("Invalid phone format. Expected 2547XXXXXXXX or 07XXXXXXXX")
        return cleaned

    @staticmethod
    def validate_amount(amount: float) -> float:
        if amount <= 0:
            raise ValidationError("Payment amount must be greater than 0")
        return round(amount, 2)

    @staticmethod
    def check_duplicate_transaction(transaction_id: str) -> bool:
        return PaymentTransaction.objects.filter(transaction_id=transaction_id).exists()

    @staticmethod
    def validate_callback_payload(payload: dict) -> bool:
        required_keys = ["ResultCode", "TransactionAmount", "MpesaReceiptNumber", "PhoneNumber"]
        return all(key in payload for key in required_keys)