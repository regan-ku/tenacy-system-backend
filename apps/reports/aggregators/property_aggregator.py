from django.db.models import Count, Q, Sum
from apps.properties.models import Property, Unit
from apps.reports.utils.filters import ReportFilterUtils

class PropertyAggregator:
    """
    Computes portfolio and property-level KPIs.
    """

    @staticmethod
    def get_portfolio_summary(user):
        """
        Returns high-level portfolio stats: total properties, total capacity, and active units.
        """
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {"total_properties": 0, "total_capacity": 0, "active_properties": 0}

        stats = Property.objects.filter(id__in=property_ids).aggregate(
            total_properties=Count('id'),
            active_properties=Count('id', filter=Q(is_active=True)),
            total_capacity=Sum('total_units_capacity')
        )

        return {
            "total_properties": stats['total_properties'] or 0,
            "active_properties": stats['active_properties'] or 0,
            "total_capacity": stats['total_capacity'] or 0
        }

    @staticmethod
    def get_unit_type_distribution(user):
        """
        Returns a breakdown of units by type (e.g., 1 Bedroom, 2 Bedroom) for charting.
        """
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        distribution = Unit.objects.filter(property_id__in=property_ids).values('unit_type').annotate(
            count=Count('id')
        ).order_by('-count')

        return [{"label": item['unit_type'], "value": item['count']} for item in distribution]