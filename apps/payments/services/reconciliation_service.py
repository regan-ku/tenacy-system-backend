from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Payment, Invoice, Reconciliation, ReconciliationStatus
from .invoice_service import InvoiceService

class ReconciliationService:
    @staticmethod
    @transaction.atomic
    def match_payment_to_invoice(payment_id: str, invoice_id: str, notes=""):
        """
        Manually or programmatically links a payment to an invoice.
        Checks for discrepancies (e.g., Payment < Invoice Balance).
        """
        payment = Payment.objects.get(id=payment_id)
        invoice = Invoice.objects.get(id=invoice_id)

        if payment.status != "completed":
            raise ValidationError("Cannot reconcile a payment that is not completed.")

        # Create Reconciliation Record
        diff = payment.amount - invoice.balance_due
        status = ReconciliationStatus.MATCHED
        
        if diff < 0:
            status = ReconciliationStatus.MISMATCH  # Underpaid
        elif diff > 0:
            status = ReconciliationStatus.MISMATCH  # Overpaid

        reconciliation = Reconciliation.objects.create(
            payment=payment,
            invoice=invoice,
            status=status,
            discrepancy_amount=abs(diff),
            notes=notes
        )

        # Update Invoice Status if fully covered
        if invoice.balance_due <= 0 and invoice.status != "paid":
            InvoiceService.update_invoice_status(invoice.id)
            
            # ✅ NEW: Check if the tenancy can now be activated!
            # This triggers the check to see if BOTH deposit and service charge are paid.
            if hasattr(invoice, 'tenancy') and invoice.tenancy:
                from tenancy.services.tenancy_state_service import TenancyStateService
                TenancyStateService.check_and_activate_tenancy(invoice.tenancy)

        return reconciliation

    @staticmethod
    def flag_unallocated_payment(payment_id, reason="No matching invoice found"):
        """Flags a payment as unallocated for manual review."""
        payment = Payment.objects.get(id=payment_id)
        return Reconciliation.objects.create(
            payment=payment,
            status=ReconciliationStatus.UNALLOCATED,
            notes=reason
        )