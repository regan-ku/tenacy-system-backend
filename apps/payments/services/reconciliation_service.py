from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Payment, Invoice, Reconciliation, ReconciliationStatus, PaymentStatus
from .invoice_service import InvoiceService
from .allocation_service import AllocationService

class ReconciliationService:
    @staticmethod
    @transaction.atomic
    def match_payment_to_invoice(payment_id: str, invoice_id: str, notes=""):
        """
        Manually reconciles a cash/bank payment to an invoice.
        Triggers the AllocationService to handle advance payments and push next_billing_date.
        """
        payment = Payment.objects.get(id=payment_id)
        invoice = Invoice.objects.get(id=invoice_id)
        tenancy = invoice.tenancy

        if payment.status not in [PaymentStatus.PENDING, "pending_reconciliation", "pending"]:
            raise ValidationError("Cannot reconcile a payment that is already completed or failed.")

        # 1. Create Reconciliation Record
        diff = payment.amount - invoice.balance_due
        status = ReconciliationStatus.MATCHED
        
        if diff < 0:
            status = ReconciliationStatus.MISMATCH  # Underpaid
        elif diff > 0:
            status = ReconciliationStatus.MISMATCH  # Overpaid (will go to future credit via AllocationService)

        reconciliation = Reconciliation.objects.create(
            payment=payment,
            invoice=invoice,
            status=status,
            discrepancy_amount=abs(diff),
            notes=notes
        )

        # 2. ✅ CRITICAL: Route through AllocationService to handle advance credits & next_billing_date
        AllocationService.allocate_payment_to_tenancy(payment, tenancy)
        
        # 3. Mark payment as fully completed
        payment.status = PaymentStatus.COMPLETED
        payment.save(update_fields=["status"])

        # 4. Update Invoice Status if fully covered
        if invoice.balance_due <= 0 and invoice.status != "paid":
            InvoiceService.update_invoice_status(invoice.id)
            
            # Check if the tenancy can now be activated (Deposit + Service Charge paid)
            if tenancy:
                from apps.tenancy.services.tenancy_state_service import TenancyStateService
                TenancyStateService.check_and_activate_tenancy(tenancy)

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