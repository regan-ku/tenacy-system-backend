from django.db.models import Count, Q, Sum
from apps.properties.models import Property, Unit
from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

class PropertyAggregator:
    """
    Computes portfolio and property-level KPIs.
    """

    @staticmethod
    def get_landlord_kpis(user):
        """
        ✅ NEW LOGIC: Calculates high-level KPIs for the Landlord Dashboard.
        This matches the frontend LandlordKPIs interface exactly.
        """
        from apps.payments.models import Payment, Invoice
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {
                "total_properties": 0,
                "total_units": 0,
                "overall_occupancy": 0,
                "total_income": 0,
                "total_arrears": 0
            }

        # 1. Total Properties
        total_properties = accessible_properties.count()

        # 2. Total Units & Occupancy
        # ✅ FIX: Changed property_id to property_ref_id to match your Unit model's ForeignKey
        unit_stats = Unit.objects.filter(property_ref_id__in=property_ids).aggregate(
            total_units=Count('id'),
            occupied_units=Count('id', filter=Q(status='occupied'))
        )
        total_units = unit_stats['total_units'] or 0
        occupied_units = unit_stats['occupied_units'] or 0
        overall_occupancy = CalculationUtils.calculate_occupancy_rate(occupied_units, total_units)

        # 3. Total Income (Revenue)
        # Note: Tenancy uses 'property' as FK, so tenancy__property_id is correct here
        total_income_data = Payment.objects.filter(
            status='success',
            allocations__invoice__tenancy__property_id__in=property_ids
        ).aggregate(total=Sum('amount'))
        total_income = float(total_income_data['total'] or 0.0)

        # 4. Total Arrears
        total_arrears_data = Invoice.objects.filter(
            tenancy__property_id__in=property_ids,
            status__in=['pending', 'partial', 'overdue']
        ).aggregate(total=Sum('balance_due'))
        total_arrears = float(total_arrears_data['total'] or 0.0)

        return {
            "total_properties": total_properties,
            "total_units": total_units,
            "overall_occupancy": overall_occupancy,
            "total_income": total_income,
            "total_arrears": total_arrears
        }

    @staticmethod
    def get_portfolio_summary(user):
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
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        # ✅ FIX: Changed property_id to property_ref_id to match your Unit model's ForeignKey
        distribution = Unit.objects.filter(property_ref_id__in=property_ids).values('unit_type').annotate(
            count=Count('id')
        ).order_by('-count')

        return [{"label": item['unit_type'], "value": item['count']} for item in distribution]

    @staticmethod
    def get_portfolio_metrics(user):
        """
        Returns per-property metrics: occupancy, rent collected, arrears, open maintenance.
        """
        from apps.payments.models import Payment, Invoice
        from apps.maintenance.models import MaintenanceRequest
        
        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        
        metrics = []
        for prop in accessible_properties:
            # Note: prop.units works because the Unit model has related_name='units' on the property_ref FK
            total_units = prop.units.count()
            occupied_units = prop.units.filter(status='occupied').count()
            occupancy_rate = CalculationUtils.calculate_occupancy_rate(occupied_units, total_units)
            
            revenue = Payment.objects.filter(
                status='success',
                allocations__invoice__tenancy__property=prop
            ).aggregate(total=Sum('amount'))['total'] or 0.0
            
            arrears = Invoice.objects.filter(
                tenancy__property=prop,
                status__in=['pending', 'partial', 'overdue']
            ).aggregate(total=Sum('balance_due'))['total'] or 0.0
            
            open_maint = MaintenanceRequest.objects.filter(
                property=prop,
                status__in=['open', 'assigned', 'in_progress', 'pending']
            ).count()
            
            landlord_name = "Unknown"
            if prop.created_by:
                landlord_name = prop.created_by.get_full_name() if hasattr(prop.created_by, 'get_full_name') and prop.created_by.get_full_name() else prop.created_by.email
            
            metrics.append({
                "property_name": prop.title,
                "landlord_name": landlord_name,
                "total_units": total_units,
                "occupancy_rate": occupancy_rate,
                "rent_collected": float(revenue),
                "arrears": float(arrears),
                "maintenance_open": open_maint
            })
        return metrics