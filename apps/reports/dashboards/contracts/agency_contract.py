from .shared_blocks import SharedDashboardBlocks

class AgencyDashboardContract:
    """
    Defines the data requirements for the Agency dashboard.
    Focuses on multi-landlord portfolios, staff workload, and delegated property performance.
    """

    @staticmethod
    def get_contract_data(user):
        """
        Assembles the exact data payload required by the Agency dashboard UI.
        Automatically scoped to the properties delegated to this agency.
        """
        return {
            "role": "agency",
            "required_widgets": [
                {
                    "id": "portfolio_overview",
                    "type": "kpi_card",
                    "title": "Managed Portfolio Overview",
                    "data_source": "property_aggregator.get_portfolio_summary"
                },
                {
                    "id": "collection_efficiency",
                    "type": "chart",
                    "title": "Rent Collection Efficiency",
                    "data_source": "payment_aggregator.get_financial_summary"
                },
                {
                    "id": "staff_workload",
                    "type": "table",
                    "title": "Agent & Caretaker Workload",
                    "data_source": "maintenance_aggregator.get_maintenance_summary"
                },
                {
                    "id": "application_pipeline",
                    "type": "kpi_card",
                    "title": "Pending Applications",
                    "data_source": "application_aggregator.get_application_pipeline_summary"
                },
                {
                    "id": "landlord_performance",
                    "type": "table",
                    "title": "Top Performing Delegated Properties",
                    "data_source": "property_aggregator.get_unit_type_distribution" # Adapted for performance
                }
            ],
            "data_blocks": {
                "financials": SharedDashboardBlocks.get_financial_kpis(user),
                "occupancy": SharedDashboardBlocks.get_occupancy_kpis(user),
                "maintenance": SharedDashboardBlocks.get_maintenance_alerts(user),
                "applications": SharedDashboardBlocks.get_application_pipeline(user)
            }
        }