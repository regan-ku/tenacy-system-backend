from decimal import Decimal
from django.db import transaction
from ..models import Payment, PaymentAllocation, AllocationType, Arrears, TenantBalance
from .invoice_service import InvoiceService
from ..utils.calculators import PaymentCalculator

class AllocationService:
    @staticmethod
    @transaction.atomic
    def allocate_payment_to_tenancy(payment: Payment, tenancy):
        """
        Distributes payment amount following strict priority rules:
        1. Clear oldest arrears
        2. Pay current invoice(s)
        3. Excess → tenant future credit
        Updates Invoice balances, Arrears record, and TenantBalance atomically.
        """
        amount = payment.amount
        if amount <= Decimal("0.00"):
            return {"status": "skipped", "reason": "Zero amount"}

        # Fetch current financial state
        arrears_record = tenancy.arrears_record
        balance_record = tenancy.balance_record
        current_invoice = tenancy.invoices.filter(status__in=["pending", "partial"]).order_by("due_date").first()

        arrears_bal = arrears_record.total_outstanding if arrears_record else Decimal("0.00")
        invoice_due = current_invoice.balance_due if current_invoice else Decimal("0.00")

        # Calculate priority split
        split = PaymentCalculator.allocate_payment(amount, arrears_bal, invoice_due)

        allocations = []

        # 1. Allocate to Arrears
        if split["to_arrears"] > 0:
            allocations.append(PaymentAllocation(
                payment=payment, amount=split["to_arrears"], allocation_type=AllocationType.ARREARS
            ))
            if arrears_record:
                arrears_record.total_outstanding -= split["to_arrears"]
                arrears_record.total_outstanding = max(arrears_record.total_outstanding, Decimal("0.00"))
                arrears_record.save(update_fields=["total_outstanding"])

        # 2. Allocate to Current Invoice
        if split["to_current"] > 0 and current_invoice:
            allocations.append(PaymentAllocation(
                payment=payment, invoice=current_invoice, amount=split["to_current"], allocation_type=AllocationType.INVOICE
            ))
            current_invoice.amount_paid += split["to_current"]
            current_invoice.balance_due -= split["to_current"]
            current_invoice.save(update_fields=["amount_paid", "balance_due"])
            InvoiceService.update_invoice_status(current_invoice.id)

        # 3. Future Credit
        if split["to_future_credit"] > 0:
            allocations.append(PaymentAllocation(
                payment=payment, amount=split["to_future_credit"], allocation_type=AllocationType.FUTURE
            ))

        # Bulk save allocations
        PaymentAllocation.objects.bulk_create(allocations)

        # Update running tenant balance
        balance_record.total_paid += amount
        balance_record.current_balance = balance_record.total_paid - balance_record.total_invoiced
        balance_record.save(update_fields=["total_paid", "current_balance", "last_updated"])

        return {"status": "allocated", "split": {k: str(v) for k, v in split.items()}}