from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.tenancy.models import Tenancy
from ..models import TenantBalance, InvoiceStatus
from .billing_cycle_service import BillingCycleService
from .invoice_service import InvoiceService
from ..utils.calculators import PaymentCalculator
import logging

logger = logging.getLogger(__name__)

class BillingService:
    @staticmethod
    @transaction.atomic
    def generate_recurring_invoices(target_date: timezone.datetime.date = None) -> dict:
        """
        Bulk scheduler entry point. Finds all active tenancies due for billing today.
        ✅ FIX: Now checks `next_billing_date` to respect advance payments.
        """
        run_date = target_date or timezone.now().date()
        billed_count = 0

        # ✅ CRITICAL FIX: Only fetch tenancies where the next billing date has arrived
        tenancies = Tenancy.objects.filter(
            status="active",
            next_billing_date__lte=run_date
        ).select_related("unit", "unit__unit_group", "tenant")

        for tenancy in tenancies:
            try:
                BillingService.create_invoice_for_tenancy(tenancy, run_date)
                billed_count += 1
            except Exception as e:
                logger.error(f"Billing failed for Tenancy {tenancy.id}: {str(e)}")

        return {"status": "completed", "billed_count": billed_count, "run_date": str(run_date)}

    @staticmethod
    @transaction.atomic
    def create_invoice_for_tenancy(tenancy: Tenancy, period_start: timezone.datetime.date) -> object:
        """
        Generates a single invoice for a tenancy based on its inherited billing cycle.
        """
        # 1. Resolve cycle configuration
        cycle = getattr(tenancy, 'billing_cycle', None) or getattr(tenancy.unit.unit_group, 'billing_cycle', None)
        if not cycle:
            raise ValueError(f"Tenancy {tenancy.id} has no billing cycle configured.")
            
        config = BillingCycleService.get_cycle_config(cycle.cycle_type)
        
        # 2. Calculate billing period boundaries
        period_end = BillingCycleService.calculate_next_billing_date(period_start, cycle.cycle_type, config["billing_day"]) - timedelta(days=1)
        due_date = period_end + timedelta(days=config["grace_period_days"])

        # 3. Determine base amount & apply proration if mid-cycle move-in
        base_rent = tenancy.rent_amount or tenancy.unit.rent_price
        amount = base_rent

        if tenancy.start_date > period_start:
            days_in_period = (period_end - period_start).days + 1
            days_occupied = (period_end - tenancy.start_date).days + 1
            amount = PaymentCalculator.prorate_amount(base_rent, days_in_period, days_occupied)

        # 4. Structure line items
        line_items = [
            {
                "item_type": "rent", 
                "description": f"Base Rent | {period_start.strftime('%B')} {period_start.year}", 
                "amount": amount, 
                "quantity": 1
            }
        ]

        # 5. Create invoice
        invoice = InvoiceService.create_invoice(
            tenancy=tenancy,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            line_items=line_items
        )

        # 6. Update tenant running balance
        BillingService._update_tenant_balance(tenancy, amount)

        # 7. ✅ NEW: Check if tenant has unallocated credit to auto-pay this invoice
        balance, _ = TenantBalance.objects.get_or_create(tenancy=tenancy)
        if balance.current_balance < 0: # Negative balance means they have credit
            credit_available = abs(balance.current_balance)
            if credit_available >= invoice.total_amount:
                # Auto-allocate credit to this invoice
                invoice.amount_paid = invoice.total_amount
                invoice.balance_due = Decimal("0.00")
                invoice.status = InvoiceStatus.PAID
                invoice.save(update_fields=["amount_paid", "balance_due", "status"])
                
                # Recalculate balance
                balance.total_paid += invoice.total_amount
                balance.current_balance = balance.total_invoiced - balance.total_paid
                balance.save(update_fields=["total_paid", "current_balance"])
                
                logger.info(f"Invoice {invoice.invoice_number} auto-paid via advance credit.")

        # 8. Advance tenancy billing cursor
        tenancy.next_billing_date = period_end + timedelta(days=1)
        tenancy.save(update_fields=["next_billing_date"])

        logger.info(f"Invoice {invoice.invoice_number} generated for Tenancy {tenancy.id} | Amount: {amount}")
        return invoice

    @staticmethod
    def _update_tenant_balance(tenancy, invoiced_amount: Decimal):
        """Atomically increments total_invoiced and recalculates current_balance."""
        balance, _ = TenantBalance.objects.get_or_create(tenancy=tenancy)
        balance.total_invoiced += invoiced_amount
        # current_balance = total_invoiced - total_paid (Positive = Owed, Negative = Credit)
        balance.current_balance = balance.total_invoiced - balance.total_paid
        balance.save(update_fields=["total_invoiced", "current_balance", "last_updated"])