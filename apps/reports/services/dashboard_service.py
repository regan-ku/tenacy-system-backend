from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import Dashboard, DashboardWidget, DashboardSnapshot
from ..aggregators import (
    PaymentAggregator, TenancyAggregator, PropertyAggregator, 
    MaintenanceAggregator, ApplicationAggregator, MarketplaceAggregator
)

class DashboardService:
    """
    Dynamically builds dashboard payloads based on role-specific widget configurations.
    Maps widget data sources to the appropriate aggregator methods.
    """

    # ✅ EXPANDED: Mapping of all data_source strings to actual aggregator methods
    AGGREGATOR_MAP = {
        # Financial
        'payment_aggregator.get_financial_summary': PaymentAggregator.get_financial_summary,
        'payment_aggregator.get_landlord_statements': PaymentAggregator.get_landlord_statements,
        
        # Tenancy
        'tenancy_aggregator.get_occupancy_summary': TenancyAggregator.get_occupancy_summary,
        'tenancy_aggregator.get_upcoming_expiries': TenancyAggregator.get_upcoming_expiries,
        
        # Property
        'property_aggregator.get_portfolio_summary': PropertyAggregator.get_portfolio_summary,
        'property_aggregator.get_unit_type_distribution': PropertyAggregator.get_unit_type_distribution,
        'property_aggregator.get_portfolio_metrics': PropertyAggregator.get_portfolio_metrics,
        
        # Maintenance
        'maintenance_aggregator.get_maintenance_summary': MaintenanceAggregator.get_maintenance_summary,
        'maintenance_aggregator.get_maintenance_analytics': MaintenanceAggregator.get_maintenance_analytics,
        
        # Applications
        'application_aggregator.get_application_pipeline_summary': ApplicationAggregator.get_application_pipeline_summary,
        
        # Marketplace
        'marketplace_aggregator.get_marketplace_summary': MarketplaceAggregator.get_marketplace_summary,
        'marketplace_aggregator.get_top_performing_listings': MarketplaceAggregator.get_top_performing_listings,
    }

    @staticmethod
    def get_dashboard_data(user, role: str = None):
        """
        Fetches the dashboard configuration for the user's role and computes 
        the live data for each enabled widget.
        """
        target_role = role or user.role
        
        # 1. Get Dashboard Configuration
        try:
            dashboard_config = Dashboard.objects.get(role=target_role, is_active=True)
        except Dashboard.DoesNotExist:
            raise ValidationError(f"No active dashboard configuration found for role: {target_role}")

        # 2. Fetch enabled widgets
        widget_configs = dashboard_config.widget_configuration.get('widgets', [])
        widget_data = []

        # 3. Compute data for each widget
        for widget_cfg in widget_configs:
            widget_id = widget_cfg.get('widget_id')
            data_source = widget_cfg.get('data_source')
            
            try:
                widget_model = DashboardWidget.objects.get(id=widget_id, is_active=True)
                
                # Resolve and execute the aggregator method
                if data_source in DashboardService.AGGREGATOR_MAP:
                    aggregator_func = DashboardService.AGGREGATOR_MAP[data_source]
                    # Pass user to ensure strict data scoping
                    computed_data = aggregator_func(user)
                else:
                    computed_data = {"error": f"Unknown data source: {data_source}"}

                widget_data.append({
                    "widget_id": widget_model.id,
                    "name": widget_model.name,
                    "type": widget_model.widget_type,
                    "frontend_config": widget_model.frontend_config,
                    "data": computed_data
                })
            except DashboardWidget.DoesNotExist:
                continue # Skip if widget was deleted or disabled

        return {
            "dashboard_name": dashboard_config.name,
            "role": target_role,
            "generated_at": timezone.now().isoformat(),
            "widgets": widget_data
        }

    @staticmethod
    def cache_dashboard_snapshot(user, dashboard_data: dict):
        """
        Saves a snapshot of the dashboard data for historical comparison or caching.
        """
        DashboardSnapshot.objects.create(
            user=user,
            role_at_time=user.role,
            snapshot_data=dashboard_data
        )