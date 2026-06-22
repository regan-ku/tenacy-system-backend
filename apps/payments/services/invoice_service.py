from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Invoice, InvoiceItem, InvoiceStatus
from ..utils.invoice_generators import InvoiceGenerator

class InvoiceService:
    @staticmethod
    @transaction.atomic
    def create_invoice(tenancy, period_start, period_end, due_date, line_items: list[dict]):
        """
        Generates a new invoice with validated line items.
        Enforces: no duplicate invoices for same period, immutable after payment.
        """
        existing = Invoice.objects.filter(
            tenancy=tenancy,
            period_start=period_start,
            period_end=period_end
        ).exists()
        if existing:
            raise ValidationError("Invoice already exists for this billing period.")

        items, total = InvoiceGenerator.build_line_items(line_items)
        
        invoice = Invoice.objects.create(
            tenancy=tenancy,
            invoice_number=InvoiceGenerator.generate_invoice_number(),
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            total_amount=total,
            amount_paid=Decimal("0.00"),
            balance_due=total,
            status=InvoiceStatus.PENDING
        )

        # Create line items in bulk
        InvoiceItem.objects.bulk_create([
            InvoiceItem(invoice=invoice, **item) for item in items
        ])

        return invoice

    @staticmethod
    @transaction.atomic
    def generate_move_in_invoices(tenancy):
        """
        ✅ NEW: Generates specific one-off invoices for Deposit and Service Charge.
        These must be paid (or waived) before the tenancy can transition to 'ACTIVE'.
        """
        due_date = timezone.now().date() + timezone.timedelta(days=7) # Example: 7 days to pay move-in costs
        
        # 1. Deposit Invoice
        if tenancy.deposit_amount and tenancy.deposit_amount > 0:
            Invoice.objects.create(
                tenancy=tenancy,
                invoice_number=InvoiceGenerator.generate_invoice_number(),
                period_start=tenancy.lease_start_date,
                period_end=tenancy.lease_start_date, # One-off event
                due_date=due_date,
                total_amount=tenancy.deposit_amount,
                amount_paid=Decimal("0.00"),
                balance_due=tenancy.deposit_amount,
                status=InvoiceStatus.PENDING,
                description="Refundable Security Deposit" # Ensure your Invoice model has a description/notes field
            )
            
        # 2. Service Charge Invoice
        if tenancy.service_charge_amount and tenancy.service_charge_amount > 0:
            Invoice.objects.create(
                tenancy=tenancy,
                invoice_number=InvoiceGenerator.generate_invoice_number(),
                period_start=tenancy.lease_start_date,
                period_end=tenancy.lease_start_date, # One-off event
                due_date=due_date,
                total_amount=tenancy.service_charge_amount,
                amount_paid=Decimal("0.00"),
                balance_due=tenancy.service_charge_amount,
                status=InvoiceStatus.PENDING,
                description="Non-refundable Service Charge"
            )

    @staticmethod
    @transaction.atomic
    def update_invoice_status(invoice_id):
        """
        Recalculates balance & updates status based on allocated payments.
        PENDING → PARTIAL → PAID | OVERDUE (if past due_date)
        """
        invoice = Invoice.objects.select_related("tenancy").get(id=invoice_id)
        
        if invoice.status == InvoiceStatus.PAID:
            raise ValidationError("Invoice is already fully paid.")
            
        # Calculate actual allocated amount
        allocated = sum(al.amount for al in invoice.payment_allocations.all())
        invoice.amount_paid = allocated
        invoice.balance_due = invoice.total_amount - allocated
        
        if invoice.balance_due <= Decimal("0.00"):
            invoice.status = InvoiceStatus.PAID
        elif allocated > Decimal("0.00"):
            invoice.status = InvoiceStatus.PARTIAL
        elif timezone.now().date() > invoice.due_date:
            invoice.status = InvoiceStatus.OVERDUE
            
        invoice.save(update_fields=["amount_paid", "balance_due", "status", "updated_at"])
        return invoice

    @staticmethod
    @transaction.atomic
    def void_invoice(invoice_id, reason=""):
        """Cancels invoice. Irreversible for audit compliance."""
        invoice = Invoice.objects.get(id=invoice_id)
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.PARTIAL]:
            raise ValidationError("Cannot void invoice with recorded payments. Create refund instead.")
            
        invoice.status = InvoiceStatus.VOID
        invoice.save(update_fields=["status", "updated_at"])
        return {"status": "voided", "reason": reason}