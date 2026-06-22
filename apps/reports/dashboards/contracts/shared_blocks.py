"""
Shared data blocks used across multiple role-based dashboard contracts.
These blocks aggregate specific domain data and can be composed into different dashboards.
"""
from apps.reports.aggregators import (
    PaymentAggregator,
    TenancyAggregator,
    PropertyAggregator,
    MaintenanceAggregator,
    ApplicationAggregator
)

class SharedDashboardBlocks:
    """
    Reusable data aggregation blocks for dashboard contracts.
    Ensures consistent data logic across Admin, Landlord, and Agency dashboards.
    Each block automatically scopes data to the requesting user's permissions.
    """

    @staticmethod
    def get_financial_kpis(user):
        """Returns core financial metrics scoped to the user."""
        return PaymentAggregator.get_financial_summary(user)

    @staticmethod
    def get_occupancy_kpis(user):
        """Returns occupancy and vacancy metrics scoped to the user."""
        return TenancyAggregator.get_occupancy_summary(user)

    @staticmethod
    def get_upcoming_expiries(user, days=60):
        """Returns a list of tenancies expiring soon."""
        return TenancyAggregator.get_upcoming_expiries(user, days_threshold=days)

    @staticmethod
    def get_maintenance_alerts(user):
        """Returns high-priority, open maintenance requests."""
        return MaintenanceAggregator.get_maintenance_summary(user)

    @staticmethod
    def get_application_pipeline(user):
        """Returns pending rental and transfer applications requiring action."""
        return ApplicationAggregator.get_application_pipeline_summary(user)

    @staticmethod
    def get_portfolio_overview(user):
        """Returns high-level property portfolio stats."""
        return PropertyAggregator.get_portfolio_summary(user)