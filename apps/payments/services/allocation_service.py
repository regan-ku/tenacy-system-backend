from decimal import Decimal
from django.db import transaction
from ..models import Payment, PaymentAllocation, AllocationType, Arrears, TenantBalance
from .invoice_service import InvoiceService
from .billing_cycle_service import BillingCycleService
from ..utils.calculators import PaymentCalculator
import logging

logger = logging.getLogger(__name__)

class AllocationService:
    @staticmethod
    @transaction.atomic
    def allocate_payment_to_tenancy(payment: Payment, tenancy):
        """
        Distributes payment amount following strict priority rules (per Knowledge Base):
        1. Clear oldest arrears
        2. Pay current invoice(s) / rent
        3. Clear penalties / late fees (if applicable)
        4. Excess → tenant future credit (Pushes Next Due Date forward)
        """
        amount = payment.amount
        if amount <= Decimal("0.00"):
            return {"status": "skipped", "reason": "Zero amount"}

        # ✅ Safe fetching of related financial records
        arrears_record = getattr(tenancy, 'arrears_record', None) or Arrears.objects.filter(tenancy=tenancy).first()
        
        # Ensure TenantBalance exists (create if it's the tenant's first payment)
        balance_record = getattr(tenancy, 'balance_record', None) or TenantBalance.objects.filter(tenancy=tenancy).first()
        if not balance_record:
            balance_record = TenantBalance.objects.create(tenancy=tenancy, total_paid=Decimal("0.00"), total_invoiced=Decimal("0.00"), current_balance=Decimal("0.00"))
        
        # Note: Ensure your Invoice model has related_name='invoices' on the tenancy ForeignKey
        current_invoice = tenancy.invoices.filter(status__in=["pending", "partial", "overdue"]).order_by("due_date").first()

        arrears_bal = arrears_record.total_outstanding if arrears_record else Decimal("0.00")
        invoice_due = current_invoice.balance_due if current_invoice else Decimal("0.00")

        # Calculate priority split
        split = PaymentCalculator.allocate_payment(amount, arrears_bal, invoice_due)
        allocations = []

        # 1. Allocate to Arrears
        to_arrears = split.get("to_arrears", Decimal("0.00"))
        if to_arrears > 0 and arrears_record:
            allocations.append(PaymentAllocation(
                payment=payment, amount=to_arrears, allocation_type=AllocationType.ARREARS
            ))
            arrears_record.total_outstanding -= to_arrears
            arrears_record.total_outstanding = max(arrears_record.total_outstanding, Decimal("0.00"))
            arrears_record.save(update_fields=["total_outstanding"])

        # 2. Allocate to Current Invoice (Rent)
        to_current = split.get("to_current", Decimal("0.00"))
        if to_current > 0 and current_invoice:
            allocations.append(PaymentAllocation(
                payment=payment, invoice=current_invoice, amount=to_current, allocation_type=AllocationType.INVOICE
            ))
            current_invoice.amount_paid += to_current
            current_invoice.balance_due -= to_current
            current_invoice.save(update_fields=["amount_paid", "balance_due"])
            InvoiceService.update_invoice_status(current_invoice.id)

        # 3. Allocate to Penalties (Late Fees) - Safe fallback if calculator supports it
        to_penalties = split.get("to_penalties", Decimal("0.00"))
        if to_penalties > 0 and current_invoice:
            # Penalties are typically bundled into the invoice allocation or tracked as a separate line item
            allocations.append(PaymentAllocation(
                payment=payment, invoice=current_invoice, amount=to_penalties, allocation_type=AllocationType.INVOICE
            ))
            current_invoice.amount_paid += to_penalties
            current_invoice.balance_due -= to_penalties
            current_invoice.save(update_fields=["amount_paid", "balance_due"])

        # 4. Future Credit (Smart Next Due Date Logic)
        to_future_credit = split.get("to_future_credit", Decimal("0.00"))
        if to_future_credit > 0:
            allocations.append(PaymentAllocation(
                payment=payment, amount=to_future_credit, allocation_type=AllocationType.FUTURE
            ))
            
            # Calculate how many full billing cycles this credit covers
            rent_amount = tenancy.rent_amount or getattr(getattr(tenancy, 'unit', None), 'rent_price', Decimal("0.00"))
            
            if rent_amount and rent_amount > 0:
                cycles_covered = int(to_future_credit // rent_amount)
                
                if cycles_covered > 0:
                    # Resolve billing cycle config safely
                    unit = getattr(tenancy, 'unit', None)
                    unit_group = getattr(unit, 'unit_group', None) if unit else None
                    
                    cycle = getattr(tenancy, 'billing_cycle', None) or getattr(unit_group, 'billing_cycle', None)
                    
                    if cycle:
                        try:
                            config = BillingCycleService.get_cycle_config(cycle.cycle_type)
                            current_next = tenancy.next_billing_date or tenancy.start_date
                            
                            # Push the date forward by the number of cycles covered
                            for _ in range(cycles_covered):
                                current_next = BillingCycleService.calculate_next_billing_date(
                                    current_next, cycle.cycle_type, config.get("billing_day", 1)
                                )
                            
                            tenancy.next_billing_date = current_next
                            tenancy.save(update_fields=['next_billing_date'])
                            logger.info(f"Advanced next billing date for tenancy {tenancy.id} by {cycles_covered} cycles.")
                        except Exception as e:
                            logger.warning(f"Could not advance billing date for tenancy {tenancy.id}: {str(e)}")

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