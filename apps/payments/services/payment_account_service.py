from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import PaymentAccount
from ..models.payment_account import AccountType
import logging

logger = logging.getLogger(__name__)


class PaymentAccountService:
    """
    PLATFORM SETTLEMENT MODEL
    -------------------------
    Manages the lifecycle of settlement/payout accounts for landlords and agencies.
    These accounts are used by the platform to send collected rent via B2C payouts.
    """

    @staticmethod
    @transaction.atomic
    def create_account(owner, property=None, account_type=None, account_name=None,
                       paybill_number=None, till_number=None, phone_number=None, is_default=False):
        """
        Creates a new settlement/payout account for a landlord or agency.
        Enforces: only one default per property, valid type mapping, owner association.
        """
        if not account_name:
            raise ValidationError("Account name is required.")

        # ✅ FIX: Use AccountType.choices instead of non-existent ACCOUNT_TYPE_CHOICES
        valid_types = [choice[0] for choice in AccountType.choices]
        if account_type not in valid_types:
            raise ValidationError(f"Invalid account type. Must be one of: {valid_types}")

        # Validate fields based on type
        if account_type == AccountType.PAYBILL and not paybill_number:
            raise ValidationError("Paybill number is required for Paybill accounts.")
        if account_type == AccountType.TILL and not till_number:
            raise ValidationError("Till number is required for Till accounts.")
        if account_type == AccountType.PHONE and not phone_number:
            raise ValidationError("Phone number is required for Direct Phone accounts.")

        # Enforce single default per property
        if is_default and property:
            PaymentAccount.objects.filter(
                property=property, is_default=True
            ).update(is_default=False)
        elif is_default and not property:
            # Global default for user (landlord/agency level)
            PaymentAccount.objects.filter(
                owner=owner, property__isnull=True, is_default=True
            ).update(is_default=False)

        account = PaymentAccount.objects.create(
            owner=owner,
            property=property,
            account_type=account_type,
            account_name=account_name,
            paybill_number=paybill_number,
            till_number=till_number,
            phone_number=phone_number,
            is_default=is_default,
            is_active=False,  # ✅ Must pass platform verification first
            is_verified=False
        )

        logger.info(
            f"Settlement account created: {account.account_name} for owner {owner.id}"
        )
        return account

    @staticmethod
    def get_active_settlement_account(owner_id, property_obj=None):
        """
        Returns the verified, active settlement account for platform payouts.
        Used when the platform needs to send collected rent to the landlord/agency.

        Priority:
        1. Property-specific settlement account (if linked)
        2. Owner's global default settlement account
        """
        qs = PaymentAccount.objects.filter(
            owner_id=owner_id, is_active=True, is_verified=True
        )

        if property_obj:
            # 1. Check for property-specific settlement account
            prop_account = (
                qs.filter(property=property_obj, is_default=True).first()
                or qs.filter(property=property_obj).first()
            )
            if prop_account:
                return prop_account

        # 2. Fallback to owner's global default settlement account
        return (
            qs.filter(property__isnull=True, is_default=True).first()
            or qs.filter(property__isnull=True).first()
        )

    @staticmethod
    @transaction.atomic
    def suspend_account(account_id, suspended_by_user, reason=""):
        """
        Suspends a settlement account due to fraud suspicion or compliance issues.
        Prevents any further payouts until re-verified.
        """
        try:
            account = PaymentAccount.objects.get(id=account_id)
        except PaymentAccount.DoesNotExist:
            raise ValidationError("Payment account not found.")

        account.is_active = False
        account.verification_status = "suspended"
        account.last_modified_by = suspended_by_user
        account.save(update_fields=["is_active", "verification_status", "last_modified_by"])

        logger.warning(
            f"Settlement account suspended: {account.account_name} "
            f"(reason: {reason or 'unspecified'})"
        )
        return account

    @staticmethod
    @transaction.atomic
    def reactivate_account(account_id, reactivated_by_user):
        """
        Re-activates a previously suspended account.
        Requires the account to still be verified.
        """
        try:
            account = PaymentAccount.objects.get(id=account_id)
        except PaymentAccount.DoesNotExist:
            raise ValidationError("Payment account not found.")

        if not account.is_verified:
            raise ValidationError(
                "Cannot reactivate an unverified account. Re-verification required."
            )

        account.is_active = True
        account.verification_status = "verified"
        account.last_modified_by = reactivated_by_user
        account.save(update_fields=["is_active", "verification_status", "last_modified_by"])

        logger.info(f"Settlement account reactivated: {account.account_name}")
        return account