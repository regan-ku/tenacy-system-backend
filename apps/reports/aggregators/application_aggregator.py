from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from django.apps import apps

from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

class ApplicationAggregator:
    """
    Computes application pipeline and conversion KPIs for dashboards and reports.
    """

    @staticmethod
    def get_application_pipeline_summary(user):
        """
        Returns counts of pending, approved, and rejected applications scoped to the user's properties.
        """
        Property = apps.get_model('properties', 'Property')
        Application = apps.get_model('applications', 'Application')
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {"pending": 0, "approved": 0, "rejected": 0, "conversion_rate": 0.0}

        stats = Application.objects.filter(property_id__in=property_ids).aggregate(
            pending=Count('id', filter=Q(status__in=['pending', 'under_review', 'escalated'])),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected'))
        )

        pending = stats['pending'] or 0
        approved = stats['approved'] or 0
        rejected = stats['rejected'] or 0
        
        total_processed = approved + rejected
        conversion_rate = CalculationUtils.calculate_percentage(approved, total_processed) if total_processed > 0 else 0.0

        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "conversion_rate": conversion_rate
        }

    @staticmethod
    def get_application_trend(user, days=30):
        """
        Returns daily application submission counts for the last N days for charting.
        """
        Property = apps.get_model('properties', 'Property')
        Application = apps.get_model('applications', 'Application')
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)
        
        if not property_ids:
            return {"labels": [], "data": []}

        cutoff_date = timezone.now() - timedelta(days=days)
        
        # ✅ REAL IMPLEMENTATION: Group by date using TruncDate
        trend_data = Application.objects.filter(
            property_id__in=property_ids,
            created_at__gte=cutoff_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        labels = [item['date'].strftime('%Y-%m-%d') for item in trend_data]
        data = [item['count'] for item in trend_data]
        
        return {"labels": labels, "data": data}