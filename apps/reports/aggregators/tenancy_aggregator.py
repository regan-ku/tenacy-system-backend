from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.tenancy.models import Tenancy, Occupancy
from apps.properties.models import Property, Unit
from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

class TenancyAggregator:
    """
    Computes tenancy and occupancy KPIs for dashboards and reports.
    """

    @staticmethod
    def get_occupancy_summary(user):
        """
        Returns total units, occupied units, vacant units, and overall occupancy rate.
        """
        # 1. Scope properties
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {"total_units": 0, "occupied_units": 0, "vacant_units": 0, "occupancy_rate": 0.0}

        # 2. Count units by status
        unit_stats = Unit.objects.filter(property_id__in=property_ids).aggregate(
            total=Count('id'),
            occupied=Count('id', filter=Q(status='occupied')),
            vacant=Count('id', filter=Q(status='available'))
        )

        total_units = unit_stats['total'] or 0
        occupied_units = unit_stats['occupied'] or 0
        vacant_units = unit_stats['vacant'] or 0

        occupancy_rate = CalculationUtils.calculate_occupancy_rate(occupied_units, total_units)

        return {
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_units,
            "occupancy_rate": occupancy_rate
        }

    @staticmethod
    def get_upcoming_expiries(user, days_threshold=60):
        """
        Returns a list of tenancies expiring within the specified threshold.
        """
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        cutoff_date = timezone.now() + timedelta(days=days_threshold)

        expiring_tenancies = Tenancy.objects.filter(
            property_id__in=property_ids,
            status__in=['active', 'extended'],
            end_date__lte=cutoff_date,
            end_date__gte=timezone.now().date()
        ).select_related('tenant', 'unit', 'property').order_by('end_date')

        return [
            {
                "tenant_name": t.tenant.get_full_name(),
                "unit_code": t.unit.unit_code,
                "property_title": t.property.title,
                "end_date": t.end_date,
                "days_remaining": (t.end_date - timezone.now().date()).days
            }
            for t in expiring_tenancies
        ]