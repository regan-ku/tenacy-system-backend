from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Waiver, Invoice
from .invoice_service import InvoiceService
import logging

logger = logging.getLogger(__name__)

class WaiverService:
    @staticmethod
    @transaction.atomic
    def apply_waiver(invoice_id: str, amount: Decimal, reason: str, approved_by_user):
        """
        Creates an approved waiver and reduces invoice/tenant balances.
        ✅ FIX: No longer mutates `total_amount` to preserve audit trails.
        """
        invoice = Invoice.objects.select_related("tenancy").get(id=invoice_id)
        if invoice.status == "paid":
            raise ValidationError("Cannot waive a fully paid invoice.")

        amount = amount.quantize(Decimal("0.01"))
        if amount <= Decimal("0.00"):
            raise ValidationError("Waiver amount must be greater than 0.")
        
        # Cap waiver at remaining balance to prevent over-credit
        if amount > invoice.balance_due:
            amount = invoice.balance_due

        waiver = Waiver.objects.create(
            tenancy=invoice.tenancy,
            invoice=invoice,
            amount=amount,
            reason=reason,
            approved_by=approved_by_user
        )

        # ✅ FIX: Recalculate balance dynamically (Total - Paid - Waived)
        total_waived = sum(w.amount for w in invoice.financial_waivers.all())
        invoice.balance_due = max(Decimal("0.00"), invoice.total_amount - invoice.amount_paid - total_waived)
        invoice.save(update_fields=["balance_due", "updated_at"])
        
        # Re-evaluate status
        InvoiceService.update_invoice_status(invoice.id)

        # Update tenant running balance
        balance, _ = invoice.tenancy.balance_record.get_or_create(tenancy=invoice.tenancy)
        balance.total_invoiced -= amount
        balance.current_balance = balance.total_invoiced - balance.total_paid
        balance.save(update_fields=["total_invoiced", "current_balance", "last_updated"])

        logger.info(f"Waiver {waiver.id} applied | Amount: {amount} | Approved by: {approved_by_user.email}")
        return {"status": "applied", "waiver_id": str(waiver.id), "new_balance": str(invoice.balance_due)}