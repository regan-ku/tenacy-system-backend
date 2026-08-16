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

        InvoiceItem.objects.bulk_create([
            InvoiceItem(invoice=invoice, **item) for item in items
        ])

        return invoice

    @staticmethod
    @transaction.atomic
    def generate_move_in_invoice(tenancy):
        """
        ✅ UPDATED: Generates a SINGLE Move-In Invoice with Rent, Deposit, and Service Charge.
        This allows the tenant to pay everything in one M-Pesa STK push.
        """
        line_items = []
        
        # 1. First Month Rent
        if tenancy.rent_amount and tenancy.rent_amount > 0:
            line_items.append({
                "item_type": "rent", 
                "description": "First Month Rent", 
                "amount": tenancy.rent_amount, 
                "quantity": 1
            })
            
        # 2. Security Deposit
        if tenancy.deposit_amount and tenancy.deposit_amount > 0:
            line_items.append({
                "item_type": "deposit", 
                "description": "Refundable Security Deposit", 
                "amount": tenancy.deposit_amount, 
                "quantity": 1
            })
            
        # 3. Service Charge
        if tenancy.service_charge_amount and tenancy.service_charge_amount > 0:
            line_items.append({
                "item_type": "service_charge", 
                "description": "Non-refundable Service Charge", 
                "amount": tenancy.service_charge_amount, 
                "quantity": 1
            })
            
        if not line_items:
            return None

        # Set due date to 7 days from now
        due_date = timezone.now().date() + timezone.timedelta(days=7)
        
        invoice = InvoiceService.create_invoice(
            tenancy=tenancy,
            period_start=tenancy.start_date,
            period_end=tenancy.start_date, # One-off event
            due_date=due_date,
            line_items=line_items
        )
        
        return invoice

    @staticmethod
    @transaction.atomic
    def update_invoice_status(invoice_id):
        """
        Recalculates balance & updates status based on allocated payments AND waivers.
        ✅ FIX: Now accounts for waivers dynamically without mutating total_amount.
        """
        invoice = Invoice.objects.select_related("tenancy").get(id=invoice_id)
        
        if invoice.status == InvoiceStatus.PAID:
            raise ValidationError("Invoice is already fully paid.")
            
        # Calculate actual allocated amount
        allocated = sum(al.amount for al in invoice.payment_allocations.all())
        
        # ✅ FIX: Calculate total waived dynamically from Waiver model
        total_waived = sum(w.amount for w in invoice.financial_waivers.all())
        
        invoice.amount_paid = allocated
        # Balance = Total - Paid - Waived
        invoice.balance_due = max(Decimal("0.00"), invoice.total_amount - allocated - total_waived)
        
        if invoice.balance_due <= Decimal("0.00"):
            invoice.status = InvoiceStatus.PAID
        elif allocated > Decimal("0.00") or total_waived > Decimal("0.00"):
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