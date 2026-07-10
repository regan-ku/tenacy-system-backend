from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.apps import apps

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
        Property = apps.get_model('properties', 'Property')
        Unit = apps.get_model('properties', 'Unit')
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {"total_units": 0, "occupied_units": 0, "vacant_units": 0, "occupancy_rate": 0.0}

        # ✅ FIX: Changed property_id to property_ref_id to match your Unit model's ForeignKey
        unit_stats = Unit.objects.filter(property_ref_id__in=property_ids).aggregate(
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
        Property = apps.get_model('properties', 'Property')
        Tenancy = apps.get_model('tenancy', 'Tenancy')
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return []

        today = timezone.now().date()
        cutoff_date = today + timedelta(days=days_threshold)

        # Note: Tenancy model uses 'property' as FK, so property_id is correct here
        expiring_tenancies = Tenancy.objects.filter(
            property_id__in=property_ids,
            status__in=['active', 'extended'],
            end_date__lte=cutoff_date,
            end_date__gte=today
        ).select_related('tenant', 'unit', 'property').order_by('end_date')

        return [
            {
                # ✅ SAFE ACCESS: Fallback to email if get_full_name is empty
                "tenant_name": t.tenant.get_full_name() if hasattr(t.tenant, 'get_full_name') and t.tenant.get_full_name() else t.tenant.email,
                "unit_code": t.unit.unit_code if t.unit else "N/A",
                "property_title": t.property.title if t.property else "N/A",
                "end_date": t.end_date,
                "days_remaining": (t.end_date - today).days
            }
            for t in expiring_tenancies
        ]