from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models import Invoice, Arrears, ArrearsStatus

class ArrearsService:
    @staticmethod
    def update_tenancy_arrears(tenancy):
        """
        Scans all open invoices for a tenancy, calculates total overdue amount,
        and updates the Arrears record.
        """
        now = timezone.now().date()
        total_outstanding = Decimal("0.00")
        oldest_due_date = None

        # Fetch all pending, partial, or overdue invoices
        invoices = Invoice.objects.filter(tenancy=tenancy, status__in=["pending", "partial", "overdue"])

        for inv in invoices:
            if inv.balance_due > 0:
                total_outstanding += inv.balance_due
                if inv.status == "overdue" or now > inv.due_date:
                    if oldest_due_date is None or inv.due_date < oldest_due_date:
                        oldest_due_date = inv.due_date

        # Update or Create Arrears Record
        arrears_record, _ = Arrears.objects.get_or_create(tenancy=tenancy)
        arrears_record.total_outstanding = total_outstanding
        arrears_record.oldest_overdue_date = oldest_due_date
        
        # Calculate days overdue
        if oldest_due_date:
            arrears_record.days_overdue = (now - oldest_due_date).days
            if arrears_record.days_overdue > 30:  # Example threshold
                arrears_record.status = ArrearsStatus.ESCALATED
            else:
                arrears_record.status = ArrearsStatus.OVERDUE
        else:
            arrears_record.days_overdue = 0
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