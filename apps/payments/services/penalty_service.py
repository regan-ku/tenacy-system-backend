from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models import Penalty, PenaltyType, InvoiceStatus
from ..services.invoice_service import InvoiceService
from ..services.arrears_service import ArrearsService
from ..utils.calculators import PaymentCalculator
import logging

logger = logging.getLogger(__name__)

class PenaltyService:
    @staticmethod
    @transaction.atomic
    def apply_late_penalty(invoice_id: str, daily_rate_percent: Decimal = Decimal("0.5")):
        """
        Applies late fee to overdue invoices.
        ✅ FIX: Now generates a Penalty Invoice so the tenant can pay it via M-Pesa.
        """
        from ..models import Invoice
        invoice = Invoice.objects.select_related("tenancy").get(id=invoice_id)
        
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.VOID, InvoiceStatus.CANCELLED]:
            return {"status": "skipped", "reason": "Invoice not eligible for penalty"}

        now = timezone.now().date()
        if now <= invoice.due_date:
            return {"status": "skipped", "reason": "Invoice not yet overdue"}

        days_overdue = (now - invoice.due_date).days
        if days_overdue <= 0:
            return {"status": "skipped"}

        # Calculate penalty using utility
        amount = PaymentCalculator.calculate_late_fee(invoice.balance_due, days_overdue, daily_rate_percent)
        if amount <= Decimal("0.00"):
            return {"status": "skipped"}

        # 1. Create the Penalty Record (Audit Trail)
        penalty = Penalty.objects.create(
            tenancy=invoice.tenancy,
            penalty_type=PenaltyType.LATE_FEE,
            amount=amount,
            reason=f"Late fee for {invoice.invoice_number} | {days_overdue} days overdue"
        )

        # 2. ✅ Generate a Penalty Invoice so tenant can pay it
        line_items = [
            {
                "item_type": "late_fee",
                "description": f"Late Penalty: {days_overdue} days overdue on {invoice.invoice_number}",
                "amount": amount,
                "quantity": 1
            }
        ]
        
        # Penalty is due immediately (or within grace period)
        due_date = now + timezone.timedelta(days=3) 
        
        penalty_invoice = InvoiceService.create_invoice(
            tenancy=invoice.tenancy,
            period_start=now,
            period_end=now,
            due_date=due_date,
            line_items=line_items
        )

        # 3. Update Arrears to include this new penalty
        ArrearsService.update_tenancy_arrears(invoice.tenancy)

        logger.info(f"Penalty {penalty.id} applied & invoiced | Amount: {amount}")
        return {
            "status": "applied", 
            "penalty_id": str(penalty.id), 
            "penalty_invoice_id": str(penalty_invoice.id),
            "amount": str(amount)
        }