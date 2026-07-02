from django.db.models import Count, Q, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from datetime import timedelta

from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

class MaintenanceAggregator:
    """
    Computes maintenance and field operation KPIs for dashboards and reports.
    """

    @staticmethod
    def get_maintenance_summary(user):
        """
        Returns total, open, resolved, and overdue maintenance requests scoped to the user.
        """
        from apps.maintenance.models import MaintenanceRequest
        from apps.properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)
        
        if not property_ids:
            return {"total_requests": 0, "open_requests": 0, "resolved_requests": 0, "overdue_requests": 0, "resolution_rate": 0.0}

        stats = MaintenanceRequest.objects.filter(property_id__in=property_ids).aggregate(
            total=Count('id'),
            open=Count('id', filter=Q(status__in=['open', 'assigned', 'in_progress', 'pending'])),
            resolved=Count('id', filter=Q(status__in=['resolved', 'closed', 'completed'])),
            # Assuming 'sla_deadline' field exists on MaintenanceRequest model
            overdue=Count('id', filter=Q(status__in=['open', 'assigned', 'in_progress', 'pending'], sla_deadline__lt=timezone.now()))
        )
        
        total = stats['total'] or 0
        resolved = stats['resolved'] or 0
        resolution_rate = CalculationUtils.calculate_percentage(resolved, total)
        
        return {
            "total_requests": total,
            "open_requests": stats['open'] or 0,
            "resolved_requests": resolved,
            "overdue_requests": stats['overdue'] or 0,
            "resolution_rate": resolution_rate
        }

    @staticmethod
    def get_average_resolution_time(user, days=30):
        """
        Calculates the average time (in days) to resolve maintenance requests.
        """
        from apps.maintenance.models import MaintenanceRequest
        from apps.properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        avg_time = MaintenanceRequest.objects.filter(
            property_id__in=property_ids,
            status__in=['resolved', 'closed', 'completed'],
            resolved_at__gte=cutoff_date
        ).annotate(
            duration=ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
        ).aggregate(avg_duration=Avg('duration'))
        
        avg_days = 0.0
        if avg_time['avg_duration']:
            avg_days = avg_time['avg_duration'].total_seconds() / 86400 # Convert seconds to days
            
        return {"average_days": round(avg_days, 1), "period": f"Last {days} days"}

    @staticmethod
    def get_requests_by_category(user):
        """
        Returns a breakdown of maintenance requests by category for charting.
        """
        from apps.maintenance.models import MaintenanceRequest
        from apps.properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)
        
        distribution = MaintenanceRequest.objects.filter(
            property_id__in=property_ids
        ).values('category').annotate(count=Count('id')).order_by('-count')
        
        return [{"label": item['category'], "value": item['count']} for item in distribution]

    # ✅ NEW: SLA ANALYTICS FOR AGENCY INTELLIGENCE
    @staticmethod
    def get_maintenance_analytics(user):
        """
        Returns SLA compliance and resolution times based on priority rules.
        """
        from apps.maintenance.models import MaintenanceRequest
        from apps.properties.models import Property
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)
        
        requests = MaintenanceRequest.objects.filter(property_id__in=property_ids)
        total_requests = requests.count()
        
        resolved = requests.filter(status__in=['resolved', 'closed', 'completed'])
        
        breached_sla = 0
        total_duration_hours = 0
        resolved_count = 0
        
        # SLA limits in hours based on system documentation
        sla_hours_map = {
            'emergency': 2,
            'high': 24,
            'medium': 72,
            'low': 168
        }
        
        for req in resolved:
            if req.resolved_at and req.created_at:
                duration = req.resolved_at - req.created_at
                duration_hours = duration.total_seconds() / 3600
                total_duration_hours += duration_hours
                resolved_count += 1
                
                sla_limit = sla_hours_map.get(req.priority, 72) # Default to medium
                if duration_hours > sla_limit:
                    breached_sla += 1
                    
        resolved_within_sla = resolved_count - breached_sla
        avg_resolution_time_hours = (total_duration_hours / resolved_count) if resolved_count > 0 else 0.0
        
        return {
            "total_requests": total_requests,
            "resolved_within_sla": resolved_within_sla,
            "breached_sla": breached_sla,
            "avg_resolution_time_hours": round(avg_resolution_time_hours, 1)
        }