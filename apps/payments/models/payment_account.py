import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# ✅ CRITICAL FIX: Save reference to Python's built-in `property` decorator
# BEFORE it gets shadowed by the ForeignKey field named `property` below.
_property = property


class AccountType(models.TextChoices):
    PAYBILL = "paybill", "Paybill"
    TILL = "till", "Buy Goods (Till Number)"
    PHONE = "phone", "Direct Phone Number"


class PaymentAccount(models.Model):
    """
    PLATFORM SETTLEMENT MODEL
    -------------------------
    In the Platform Collection Model, the platform collects all rent via a
    single global Paybill (configured in .env). This model represents the
    LANDLORD'S or AGENCY'S payout/settlement destination.

    The platform uses these verified accounts to send collected funds back
    to the owners via B2C or bank transfer.

    RULES:
    - Only VERIFIED + ACTIVE accounts can receive payouts
    - Only ONE default account per property
    - Only ONE global default account per owner (property is NULL)
    - Account changes to critical fields trigger re-verification
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_accounts",
    )

    # Optional: link to a specific property. If NULL, this is a global
    # settlement account for the owner.
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_accounts",
    )

    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    account_name = models.CharField(max_length=200)

    # Payout details (M-Pesa)
    paybill_number = models.CharField(max_length=50, blank=True, null=True)
    till_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    is_default = models.BooleanField(
        default=False,
        help_text="Primary settlement/payout account for this property/landlord",
    )
    is_active = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20, default="pending", db_index=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_payment_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["property", "is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_per_property",
            ),
        ]
        verbose_name = "Settlement Account"
        verbose_name_plural = "Settlement Accounts"

    def __str__(self):
        return f"{self.get_account_type_display()} | {self.account_name} (Settlement)"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def clean(self):
        super().clean()

        if self.account_type == AccountType.PAYBILL and not self.paybill_number:
            raise ValidationError(
                {"paybill_number": "Paybill number is required for Paybill accounts."}
            )
        if self.account_type == AccountType.TILL and not self.till_number:
            raise ValidationError(
                {"till_number": "Till number is required for Till accounts."}
            )
        if self.account_type == AccountType.PHONE and not self.phone_number:
            raise ValidationError(
                {"phone_number": "Phone number is required for Phone accounts."}
            )

    # ------------------------------------------------------------------
    # Helpers (using _property to avoid ForeignKey shadowing)
    # ------------------------------------------------------------------
    @_property
    def settlement_identifier(self) -> str:
        """Return the primary payout identifier based on account type."""
        if self.account_type == AccountType.PAYBILL:
            return self.paybill_number or ""
        if self.account_type == AccountType.TILL:
            return self.till_number or ""
        if self.account_type == AccountType.PHONE:
            return self.phone_number or ""
        return ""

    @_property
    def can_receive_payout(self) -> bool:
        """Only verified + active accounts can receive payouts."""
        return self.is_verified and self.is_active

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        # 1. Re-verification trigger: if critical payout fields change on
        #    an already-verified account, reset verification status.
        if self.pk:
            try:
                old = PaymentAccount.objects.get(pk=self.pk)
                critical_changed = (
                    old.paybill_number != self.paybill_number
                    or old.till_number != self.till_number
                    or old.phone_number != self.phone_number
                    or old.account_type != self.account_type
                )
                if critical_changed and old.is_verified:
                    self.is_verified = False
                    self.is_active = False
                    self.verification_status = "pending"
                    self.verified_at = None
            except PaymentAccount.DoesNotExist:
                pass

        # 2. Enforce single global default per owner (property is NULL)
        if self.is_default and self.property is None:
            PaymentAccount.objects.filter(
                owner=self.owner,
                property__isnull=True,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)