from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.payments.models import Invoice, Payment
from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

class PaymentAggregator:
    """
    Computes financial KPIs for dashboards and reports.
    All queries are strictly scoped to the requesting user's property access.
    """

    @staticmethod
    def get_financial_summary(user, start_date=None, end_date=None):
        """
        Returns total revenue, outstanding arrears, and collection rate for a given period.
        """
        from properties.models import Property
        
        # 1. Scope properties to the user
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {
                "total_revenue": 0.0,
                "outstanding_arrears": 0.0,
                "total_invoices": 0,
                "collection_rate": 0.0
            }

        # 2. Build date filter
        date_filter = Q()
        if start_date:
            date_filter &= Q(created_at__gte=start_date)
        if end_date:
            date_filter &= Q(created_at__lte=end_date)

        # 3. Aggregate Revenue (Successful payments linked to scoped properties)
        revenue_data = Payment.objects.filter(
            date_filter,
            status='success',
            invoice__property_id__in=property_ids
        ).aggregate(total=Sum('amount'))
        total_revenue = float(revenue_data['total'] or 0.0)

        # 4. Aggregate Arrears (Outstanding invoice balances)
        arrears_data = Invoice.objects.filter(
            property_id__in=property_ids,
            status__in=['pending', 'partially_paid', 'overdue']
        ).aggregate(total=Sum('outstanding_balance'))
        outstanding_arrears = float(arrears_data['total'] or 0.0)

        # 5. Calculate Collection Rate
        total_expected = total_revenue + outstanding_arrears
        collection_rate = CalculationUtils.calculate_percentage(total_revenue, total_expected)

        return {
            "total_revenue": total_revenue,
            "outstanding_arrears": outstanding_arrears,
            "total_invoices": Invoice.objects.filter(property_id__in=property_ids).count(),
            "collection_rate": collection_rate
        }

    @staticmethod
    def get_revenue_trend(user, months=6):
        """
        Returns monthly revenue breakdown for the last N months for charting.
        """
        # Implementation would group payments by month using Django's TruncMonth
        # Placeholder for structural completeness
        return {"labels": [], "data": []}