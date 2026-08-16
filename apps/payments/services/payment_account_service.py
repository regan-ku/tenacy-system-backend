from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import PaymentAccount

class PaymentAccountService:
    @staticmethod
    @transaction.atomic
    def create_account(owner, property=None, account_type=None, account_name=None,
                       paybill_number=None, till_number=None, phone_number=None, is_default=False):
        """
        Creates a new payment routing account.
        Enforces: only one default per property, valid type mapping, owner association.
        """
        if not account_name:
            raise ValidationError("Account name is required.")
        if account_type not in dict(PaymentAccount.ACCOUNT_TYPE_CHOICES).keys():
            raise ValidationError("Invalid account type.")

        # Validate fields based on type
        if account_type == "paybill" and not paybill_number:
            raise ValidationError("Paybill number is required for Paybill accounts.")
        if account_type == "till" and not till_number:
            raise ValidationError("Till number is required for Till accounts.")
        if account_type == "phone" and not phone_number:
            raise ValidationError("Phone number is required for Direct Phone accounts.")

        # Enforce single default per property
        if is_default and property:
            PaymentAccount.objects.filter(property=property, is_default=True).update(is_default=False)
        elif is_default and not property:
            # Global default for user (landlord/agency level)
            PaymentAccount.objects.filter(owner=owner, property__isnull=True, is_default=True).update(is_default=False)

        account = PaymentAccount.objects.create(
            owner=owner,
            property=property,
            account_type=account_type,
            account_name=account_name,
            paybill_number=paybill_number,
            till_number=till_number,
            phone_number=phone_number,
            is_default=is_default,
            is_active=False,  # Must pass verification first
            is_verified=False
        )
        return account

    @staticmethod
    def get_active_routing_account(property_obj=None, user_id=None):
        """
        Returns the verified, active payment account for direct collection.
        ✅ UPDATED: Respects the Agency Delegation Model from the Project Write-Up.
        Priority: 
        1. Delegated Agency Account (if property is agency-managed)
        2. Property-specific Landlord Account
        3. User-level (Landlord/Agency) Default Account
        """
        qs = PaymentAccount.objects.filter(is_active=True, is_verified=True)
        
        if property_obj:
            # 1. Check if property is delegated to an agency (Assuming 'current_manager' holds the agency/manager)
            manager = getattr(property_obj, 'current_manager', None)
            if manager and getattr(manager, 'role', None) in ['agency', 'manager']:
                agency_account = qs.filter(owner=manager, is_default=True).first() or qs.filter(owner=manager).first()
                if agency_account:
                    return agency_account
            
            # 2. Fallback to property-specific landlord account
            prop_account = qs.filter(property=property_obj, is_default=True).first() or qs.filter(property=property_obj).first()
            if prop_account:
                return prop_account
                
        # 3. Fallback to global user default
        if user_id:
            return qs.filter(owner_id=user_id, property__isnull=True, is_default=True).first() or qs.filter(owner_id=user_id, property__isnull=True).first()
        
        return None