import uuid
from django.db import models
from django.conf import settings

class AccountType(models.TextChoices):
    PAYBILL = "paybill", "Paybill"
    TILL = "till", "Buy Goods (Till Number)"
    PHONE = "phone", "Direct Phone Number"

class PaymentAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_accounts")
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_accounts")
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    account_name = models.CharField(max_length=200)
    paybill_number = models.CharField(max_length=50, blank=True, null=True)
    till_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_default = models.BooleanField(default=False, help_text="Primary routing account for this property")
    is_active = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, default="pending", db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="modified_payment_accounts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["property", "is_default"], condition=models.Q(is_default=True), name="unique_default_per_property"),
        ]

    def __str__(self):
        return f"{self.get_account_type_display()} | {self.account_name}"