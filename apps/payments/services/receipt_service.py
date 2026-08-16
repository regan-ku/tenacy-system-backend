from decimal import Decimal
import uuid
from django.db import transaction
from django.utils import timezone  # ✅ FIX: Use Django's timezone, not datetime's
from ..models import Payment, Receipt, Invoice, PaymentAllocation, AllocationType
from ..utils.invoice_generators import InvoiceGenerator
import logging

logger = logging.getLogger(__name__)


class ReceiptService:
    @staticmethod
    @transaction.atomic
    def generate_receipt(payment_id, tenancy_id=None, file_url=None):
        """
        Generates a receipt only for completed payments.
        Aggregates allocation details AND waivers to show the tenant
        exactly what was paid, what was waived, and what was credited.
        """
        payment = Payment.objects.select_related('payer').get(id=payment_id)
        
        if payment.status != "completed":
            raise ValueError(
                f"Cannot generate receipt for payment {payment_id} "
                f"with status '{payment.status}'. Payment must be completed."
            )

        # ✅ Idempotency: Check if receipt already exists
        existing = Receipt.objects.filter(payment=payment).first()
        if existing:
            logger.info(f"Receipt already exists for payment {payment_id}: {existing.receipt_number}")
            return existing

        # ✅ Derive tenancy from payment allocations if not provided
        if not tenancy_id:
            first_allocation = payment.allocations.select_related('invoice__tenancy').first()
            if first_allocation and first_allocation.invoice:
                tenancy_id = first_allocation.invoice.tenancy.id
            else:
                raise ValueError(
                    f"Cannot determine tenancy for payment {payment_id}. "
                    f"Provide tenancy_id explicitly."
                )

        # Generate unique receipt number
        receipt_number = f"REC-{uuid.uuid4().hex[:8].upper()}"

        receipt = Receipt.objects.create(
            receipt_number=receipt_number,
            payment=payment,
            tenancy_id=tenancy_id,
            file_url=file_url,
            issued_at=timezone.now()
        )

        logger.info(
            f"Receipt {receipt.receipt_number} generated for payment {payment.payment_id} | "
            f"Amount: {payment.amount}"
        )
        return receipt

    @staticmethod
    def get_receipt_data(receipt_id):
        """
        Retrieves receipt data formatted for PDF generation or API response.
        ✅ UPDATED: Now includes waivers, line-item breakdown, and advance credit.
        """
        try:
            receipt = Receipt.objects.select_related(
                'payment', 'payment__payer', 'tenancy', 'tenancy__unit', 'tenancy__property'
            ).get(id=receipt_id)
        except Receipt.DoesNotExist:
            return None

        payment = receipt.payment
        tenancy = receipt.tenancy

        # ✅ 1. Build line-item breakdown from allocations
        allocated_items = []
        total_allocated = Decimal("0.00")
        total_advance_credit = Decimal("0.00")

        allocations = payment.allocations.select_related(
            'invoice'
        ).prefetch_related(
            'invoice__line_items',
            'invoice__financial_waivers'
        ).all()

        for allocation in allocations:
            if allocation.allocation_type == AllocationType.FUTURE:
                # ✅ Advance payment credit
                total_advance_credit += allocation.amount
                allocated_items.append({
                    "type": "advance_credit",
                    "description": "Advance Payment Credit (applied to future rent)",
                    "amount": str(allocation.amount),
                    "invoice_number": None,
                })
            elif allocation.invoice:
                invoice = allocation.invoice
                total_allocated += allocation.amount

                # Get line items for this invoice
                for item in invoice.line_items.all():
                    allocated_items.append({
                        "type": item.item_type,
                        "description": item.description,
                        "amount": str(item.amount),
                        "quantity": item.quantity,
                        "unit_price": str(item.unit_price) if item.unit_price else None,
                        "invoice_number": invoice.invoice_number,
                    })

                # ✅ 2. Include waivers applied to this invoice
                waivers = invoice.financial_waivers.all()
                for waiver in waivers:
                    allocated_items.append({
                        "type": "waiver",
                        "description": f"Waiver: {waiver.reason}",
                        "amount": f"-{waiver.amount}",  # Negative to show deduction
                        "invoice_number": invoice.invoice_number,
                    })

        # ✅ 3. Build the full receipt summary
        receipt_data = {
            # Receipt metadata
            "receipt_number": receipt.receipt_number,
            "receipt_id": str(receipt.id),
            "issued_at": receipt.issued_at.isoformat(),
            "payment_id": payment.payment_id,
            "payment_source": payment.source,
            "payment_date": payment.paid_at.isoformat() if payment.paid_at else None,

            # Tenant & property details
            "tenant_name": getattr(payment.payer, 'email', 'Unknown') if payment.payer else 'Unknown',
            "tenant_phone": getattr(payment.payer, 'phone_number', '') if payment.payer else '',
            "property_name": tenancy.property.title if tenancy and tenancy.property else 'N/A',
            "unit_code": tenancy.unit.unit_code if tenancy and tenancy.unit else 'N/A',

            # Financial breakdown
            "total_amount_paid": str(payment.amount),
            "total_allocated_to_invoices": str(total_allocated),
            "advance_credit": str(total_advance_credit),
            "line_items": allocated_items,

            # Invoice references
            "invoices_covered": list(set(
                item["invoice_number"] for item in allocated_items
                if item["invoice_number"] is not None
            )),

            # File URL (if PDF was generated)
            "file_url": receipt.file_url,
        }

        return receipt_data

    @staticmethod
    def get_receipt_download_data(receipt_id):
        """
        ✅ NEW: Returns receipt data specifically formatted for PDF generation.
        Separated from get_receipt_data so PDF templates can evolve independently.
        """
        data = ReceiptService.get_receipt_data(receipt_id)
        if not data:
            return None

        # Add PDF-specific formatting
        data["pdf_config"] = {
            "page_size": "A4",
            "orientation": "portrait",
            "header": {
                "title": "PAYMENT RECEIPT",
                "receipt_number": data["receipt_number"],
                "issued_date": data["issued_at"],
            },
            "footer": {
                "note": "This is a computer-generated receipt and does not require a signature.",
                "disclaimer": "For queries, contact your property manager.",
            }
        }

        return data

    @staticmethod
    @transaction.atomic
    def void_receipt(receipt_id, reason=""):
        """
        ✅ NEW: Voids a receipt (e.g., if payment was reversed or refunded).
        Maintains audit trail instead of deleting.
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise ValueError(f"Receipt {receipt_id} not found.")

        receipt.file_url = None  # Invalidate download
        receipt.notes = f"VOIDED: {reason}" if hasattr(receipt, 'notes') else reason
        receipt.save()

        logger.info(f"Receipt {receipt.receipt_number} voided | Reason: {reason}")
        return {"status": "voided", "receipt_id": str(receipt.id)}