from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models import Invoice, Arrears, ArrearsStatus, TenantBalance

class ArrearsService:
    @staticmethod
    @transaction.atomic
    def update_tenancy_arrears(tenancy):
        """
        Scans all open invoices for a tenancy, calculates total overdue amount,
        and updates the Arrears record. Respects waivers (via invoice.balance_due).
        """
        now = timezone.now().date()
        total_outstanding = Decimal("0.00")
        oldest_due_date = None

        # Fetch all pending, partial, or overdue invoices that still have a balance
        # Note: balance_due already accounts for payments AND waivers dynamically
        invoices = Invoice.objects.filter(
            tenancy=tenancy, 
            status__in=["pending", "partial", "overdue"],
            balance_due__gt=0
        )

        for inv in invoices:
            total_outstanding += inv.balance_due
            if inv.status == "overdue" or now > inv.due_date:
                if oldest_due_date is None or inv.due_date < oldest_due_date:
                    oldest_due_date = inv.due_date

        # Update or Create Arrears Record
        arrears_record, _ = Arrears.objects.get_or_create(tenancy=tenancy)
        arrears_record.total_outstanding = total_outstanding
        arrears_record.oldest_overdue_date = oldest_due_date
        
        # Calculate days overdue
        if oldest_due_date and total_outstanding > 0:
            arrears_record.days_overdue = (now - oldest_due_date).days
            if arrears_record.days_overdue > 30:
                arrears_record.status = ArrearsStatus.ESCALATED
            else:
                arrears_record.status = ArrearsStatus.OVERDUE
        else:
            # ✅ FIX: If balance is 0 (e.g. paid in advance or fully waived), clear arrears
            arrears_record.days_overdue = 0
            arrears_record.total_outstanding = Decimal("0.00")
            arrears_record.status = ArrearsStatus.CURRENT

        arrears_record.save()
        
        return arrears_record

    @staticmethod
    def get_arrears_summary(tenancy_id):
        """Quick retrieval of arrears status for dashboards."""
        try:
            return Arrears.objects.get(tenancy_id=tenancy_id)
        except Arrears.DoesNotExist:
            return None