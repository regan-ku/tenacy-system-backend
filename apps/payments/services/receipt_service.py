from datetime import timezone
import uuid
from decimal import Decimal
from django.db import transaction
from ..models import Payment, Receipt, Invoice
from ..utils.invoice_generators import InvoiceGenerator

class ReceiptService:
    @staticmethod
    @transaction.atomic
    def generate_receipt(payment_id, tenancy_id, file_url=None):
        """
        Generates a receipt only for completed payments.
        Aggregates allocation details to show the tenant exactly what was paid.
        """
        payment = Payment.objects.get(id=payment_id)
        if payment.status != "completed":
            raise Exception(f"Cannot generate receipt for payment {payment_id} with status {payment.status}")

        # Check if receipt already exists
        existing = Receipt.objects.filter(payment=payment).first()
        if existing:
            return existing

        # Generate unique number
        receipt_number = f"REC-{uuid.uuid4().hex[:6].upper()}"

        # Get allocation details for the receipt body
        allocations = list(payment.allocations.values('amount', 'allocation_type', 'invoice__invoice_number'))

        receipt = Receipt.objects.create(
            receipt_number=receipt_number,
            payment=payment,
            tenancy_id=tenancy_id,
            file_url=file_url,
            issued_at=timezone.now()
        )

        return receipt

    @staticmethod
    def get_receipt_data(receipt_id):
        """Retrieves receipt data formatted for PDF generation or API response."""
        try:
            receipt = Receipt.objects.select_related('payment', 'tenancy').get(id=receipt_id)
            return InvoiceGenerator.format_receipt_data(
                payment=receipt.payment,
                tenancy=receipt.tenancy,
                allocated_items=list(receipt.payment.allocations.all())
            )
        except Receipt.DoesNotExist:
            return None