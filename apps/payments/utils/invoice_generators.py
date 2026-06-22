import uuid
from decimal import Decimal
from typing import Dict, List, Any
from django.utils import timezone

class InvoiceGenerator:
    @staticmethod
    def generate_invoice_number() -> str:
        """Generates unique sequential-style invoice number (e.g., INV-202410-XXXXXX)"""
        now = timezone.now()
        prefix = f"INV-{now.strftime('%Y%m')}"
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"{prefix}-{unique_suffix}"

    @staticmethod
    def build_line_items(breakdown: List[Dict[str, Any]]) -> tuple[List[Dict], Decimal]:
        """
        Validates and structures line items for invoice creation.
        Returns (validated_items, total_amount)
        """
        validated_items = []
        total = Decimal("0.00")

        for item in breakdown:
            amount = Decimal(str(item.get("amount", 0)))
            qty = item.get("quantity", 1)
            
            validated_items.append({
                "item_type": item.get("type", "other"),
                "description": item.get("description", ""),
                "amount": amount.quantize(Decimal("0.01")),
                "quantity": qty,
                "unit_price": (amount / qty).quantize(Decimal("0.01")) if qty > 1 else amount.quantize(Decimal("0.01"))
            })
            total += amount

        return validated_items, total.quantize(Decimal("0.01"))

    @staticmethod
    def format_receipt_data(payment, tenancy, allocated_items: List[Dict]) -> Dict:
        """Structures payload for PDF receipt generation & tenant dashboard."""
        tenant_name = tenancy.tenant.full_name if hasattr(tenancy, "tenant") else "N/A"
        unit_code = tenancy.unit.unit_code if hasattr(tenancy, "unit") else "N/A"
        
        return {
            "receipt_number": f"REC-{payment.payment_id[:8].upper()}",
            "tenancy_code": getattr(tenancy, "tenancy_code", "N/A"),
            "payer_name": tenant_name,
            "property_unit": unit_code,
            "payment_date": payment.paid_at.strftime("%Y-%m-%d %H:%M") if payment.paid_at else "N/A",
            "payment_method": payment.get_source_display(),
            "transaction_ref": payment.payment_id,
            "allocations": allocated_items,
            "total_paid": payment.amount
        }