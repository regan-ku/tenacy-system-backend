from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models import Penalty, PenaltyType, Invoice
from ..utils.calculators import PaymentCalculator
import logging

logger = logging.getLogger(__name__)

class PenaltyService:
    @staticmethod
    @transaction.atomic
    def apply_late_penalty(invoice_id: str, daily_rate_percent: Decimal = Decimal("0.5")):
        """
        Applies late fee to overdue invoices.
        Respects grace periods defined in billing cycles.
        """
        invoice = Invoice.objects.select_related("tenancy").get(id=invoice_id)
        
        if invoice.status in ["paid", "void", "cancelled"]:
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

        penalty = Penalty.objects.create(
            tenancy=invoice.tenancy,
            penalty_type=PenaltyType.LATE_FEE,
            amount=amount,
            reason=f"Late fee for {invoice.invoice_number} | {days_overdue} days overdue"
        )

        logger.info(f"Penalty {penalty.id} applied to invoice {invoice_id} | Amount: {amount}")
        return {"status": "applied", "penalty_id": str(penalty.id), "amount": str(amount), "days_overdue": days_overdue}