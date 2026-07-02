from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncMonth
from django.contrib.auth import get_user_model

from apps.payments.models import Invoice, Payment
from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

User = get_user_model()

class PaymentAggregator:
    """
    Computes financial KPIs for dashboards and reports.
    All queries are strictly scoped to the requesting user's property access.
    """

    @staticmethod
    def get_financial_summary(user, start_date=None, end_date=None):
        from properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {
                "total_revenue": 0.0,
                "outstanding_arrears": 0.0,
                "total_invoices": 0,
                "collection_rate": 0.0
            }

        date_filter = Q()
        if start_date:
            date_filter &= Q(created_at__gte=start_date)
        if end_date:
            date_filter &= Q(created_at__lte=end_date)

        revenue_data = Payment.objects.filter(
            date_filter,
            status='success',
            allocations__invoice__tenancy__property_id__in=property_ids
        ).aggregate(total=Sum('amount'))
        total_revenue = float(revenue_data['total'] or 0.0)

        arrears_data = Invoice.objects.filter(
            tenancy__property_id__in=property_ids,
            status__in=['pending', 'partial', 'overdue']
        ).aggregate(total=Sum('balance_due'))
        outstanding_arrears = float(arrears_data['total'] or 0.0)

        total_expected = total_revenue + outstanding_arrears
        collection_rate = CalculationUtils.calculate_percentage(total_revenue, total_expected)

        return {
            "total_revenue": total_revenue,
            "outstanding_arrears": outstanding_arrears,
            "total_invoices": Invoice.objects.filter(tenancy__property_id__in=property_ids).count(),
            "collection_rate": collection_rate
        }

    @staticmethod
    def get_revenue_trend(user, months=6):
        from properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)
        
        cutoff_date = timezone.now() - timedelta(days=30 * months)
        
        trend_data = Payment.objects.filter(
            status='success',
            allocations__invoice__tenancy__property_id__in=property_ids,
            created_at__gte=cutoff_date
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        
        labels = [item['month'].strftime('%b %Y') for item in trend_data]
        data = [float(item['total'] or 0) for item in trend_data]
        
        return {"labels": labels, "data": data}

    @staticmethod
    def get_landlord_statements(user):
        """
        Generates monthly financial statements for landlords whose properties are managed by the user.
        ✅ FIXED: Only generates statements for landlords with actual financial records (gross_rent > 0).
        ✅ FIXED: Uses unique IDs to prevent duplicate React keys on the frontend.
        """
        from apps.properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        
        # ✅ 1. Get a guaranteed unique list of landlord IDs who own these properties
        landlord_ids = accessible_properties.values_list('created_by_id', flat=True).distinct()
        
        statements = []
        current_period = timezone.now().strftime('%B %Y')
        
        for landlord_id in landlord_ids:
            if not landlord_id:
                continue
            
            # ✅ 2. Safely fetch the landlord's name
            try:
                landlord = User.objects.get(id=landlord_id)
                profile = getattr(landlord, 'profile', None)
                landlord_name = getattr(profile, 'full_name', None) or landlord.get_full_name() or landlord.email
            except User.DoesNotExist:
                continue
            
            landlord_properties = accessible_properties.filter(created_by_id=landlord_id)
            property_ids = landlord_properties.values_list('id', flat=True)
            
            # Calculate gross rent
            gross_rent = Payment.objects.filter(
                status='success',
                allocations__invoice__tenancy__property_id__in=property_ids
            ).aggregate(total=Sum('amount'))['total'] or 0.0
            
            # ✅ 3. CRITICAL FIX: Skip landlords with NO financial records
            # This prevents empty statements from appearing and stops empty PDF downloads
            if gross_rent <= 0:
                continue
            
            agency_fee = gross_rent * 0.10
            net_payout = gross_rent - agency_fee
            
            statements.append({
                "id": f"ST-{landlord_id}", # Unique ID guaranteed by the distinct() query above
                "landlord_name": landlord_name,
                "period": current_period,
                "gross_rent": float(gross_rent),
                "agency_fee": float(agency_fee),
                "net_payout": float(net_payout),
                "status": "generated"
            })
            
        return statements