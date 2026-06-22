from decimal import Decimal
from django.core.exceptions import ValidationError
from ..services.payment_account_service import PaymentAccountService
from .account_validation_service import AccountValidationService
from .mpesa_service import MpesaPaymentGateway

class PaymentStkOrchestrator:
    @staticmethod
    def request_payment(tenancy, phone: str, amount: Decimal, invoice_ref: str = None) -> dict:
        """
        End-to-end STK push flow for rent/deposit collection.
        1. Validates tenancy is billable
        2. Selects & validates property routing account
        3. Triggers M-Pesa gateway
        """
        # 1. State validation
        tenancy_status = getattr(tenancy, "status", None)
        if tenancy_status not in ["active", "pending_payment", "overdue"]:
            raise ValidationError("Tenancy is not in a billable state.")

        # 2. Routing account resolution
        property_obj = getattr(tenancy, "target_property", None)
        property_id = property_obj.id if property_obj else None
        
        routing_account = PaymentAccountService.get_active_routing_account(property_id=property_id)
        if not routing_account:
            raise ValidationError("No verified payment account configured for this property.")

        # 3. Pre-flight validation
        AccountValidationService.validate_for_collection(str(routing_account.id))

        # 4. Format reference for reconciliation
        reference = invoice_ref or f"TEN-{str(tenancy.id)[:8].upper()}"
        description = f"Rent Payment - {getattr(tenancy, 'unit_code', 'Unit')}"

        # 5. Trigger gateway
        return MpesaPaymentGateway.initiate_collection(
            phone=phone,
            amount=amount,
            reference=reference,
            description=description
        )