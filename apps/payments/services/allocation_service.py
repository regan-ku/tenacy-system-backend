from decimal import Decimal
from django.db import transaction
from ..models import Payment, PaymentAllocation, AllocationType, Arrears, TenantBalance
from .invoice_service import InvoiceService
from .billing_cycle_service import BillingCycleService
from ..utils.calculators import PaymentCalculator

class AllocationService:
    @staticmethod
    @transaction.atomic
    def allocate_payment_to_tenancy(payment: Payment, tenancy):
        """
        Distributes payment amount following strict priority rules:
        1. Clear oldest arrears
        2. Pay current invoice(s)
        3. Excess → tenant future credit (Pushes Next Due Date forward)
        """
        amount = payment.amount
        if amount <= Decimal("0.00"):
            return {"status": "skipped", "reason": "Zero amount"}

        # ✅ Safe fetching of related financial records
        arrears_record = getattr(tenancy, 'arrears_record', None) or Arrears.objects.filter(tenancy=tenancy).first()
        balance_record = getattr(tenancy, 'balance_record', None) or TenantBalance.objects.filter(tenancy=tenancy).first()
        
        current_invoice = tenancy.invoices.filter(status__in=["pending", "partial"]).order_by("due_date").first()

        arrears_bal = arrears_record.total_outstanding if arrears_record else Decimal("0.00")
        invoice_due = current_invoice.balance_due if current_invoice else Decimal("0.00")

        # Calculate priority split
        split = PaymentCalculator.allocate_payment(amount, arrears_bal, invoice_due)
        allocations = []

        # 1. Allocate to Arrears
        if split["to_arrears"] > 0 and arrears_record:
            allocations.append(PaymentAllocation(
                payment=payment, amount=split["to_arrears"], allocation_type=AllocationType.ARREARS
            ))
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

        # 3. Future Credit (✅ NEW: Smart Next Due Date Logic)
        if split["to_future_credit"] > 0:
            allocations.append(PaymentAllocation(
                payment=payment, amount=split["to_future_credit"], allocation_type=AllocationType.FUTURE
            ))
            
            # Calculate how many full billing cycles this credit covers
            rent_amount = tenancy.rent_amount or getattr(tenancy.unit, 'rent_price', Decimal("0.00"))
            if rent_amount and rent_amount > 0:
                cycles_covered = int(split["to_future_credit"] // rent_amount)
                
                if cycles_covered > 0:
                    # Resolve billing cycle config
                    cycle = getattr(tenancy, 'billing_cycle', None) or getattr(tenancy.unit.unit_group, 'billing_cycle', None)
                    if cycle:
                        config = BillingCycleService.get_cycle_config(cycle.cycle_type)
                        current_next = tenancy.next_billing_date or tenancy.start_date
                        
                        # Push the date forward by the number of cycles covered
                        for _ in range(cycles_covered):
                            current_next = BillingCycleService.calculate_next_billing_date(
                                current_next, cycle.cycle_type, config["billing_day"]
                            )
                        
                        tenancy.next_billing_date = current_next
                        tenancy.save(update_fields=['next_billing_date'])

        # Bulk save allocations
        if allocations:
            PaymentAllocation.objects.bulk_create(allocations)

        # Update running tenant balance
        if balance_record:
            balance_record.total_paid += amount
            # current_balance = total_invoiced - total_paid (Positive = Owed, Negative = Credit)
            balance_record.current_balance = balance_record.total_invoiced - balance_record.total_paid
            balance_record.save(update_fields=["total_paid", "current_balance", "last_updated"])

        return {"status": "allocated", "split": {k: str(v) for k, v in split.items()}}