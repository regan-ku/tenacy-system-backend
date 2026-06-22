from .shared_blocks import SharedDashboardBlocks

class LandlordDashboardContract:
    """
    Defines the data requirements for the Landlord dashboard.
    Focuses on multi-property performance, financial health, tenant next-of-kin visibility, 
    and agency oversight (if properties are delegated).
    """

    @staticmethod
    def get_contract_data(user):
        """
        Assembles the exact data payload required by the Landlord dashboard UI.
        Automatically scoped to the properties owned by this landlord.
        """
        # Fetch aggregated data blocks scoped to the landlord
        financials = SharedDashboardBlocks.get_financial_kpis(user)
        occupancy = SharedDashboardBlocks.get_occupancy_kpis(user)
        maintenance = SharedDashboardBlocks.get_maintenance_alerts(user)
        applications = SharedDashboardBlocks.get_application_pipeline(user)

        return {
            "role": "landlord",
            "required_widgets": [
                {
                    "id": "portfolio_financials",
                    "type": "kpi_card",
                    "title": "Total Portfolio Revenue & Arrears",
                    "data_source": "payment_aggregator.get_financial_summary"
                },
                {
                    "id": "occupancy_rate",
                    "type": "chart",
                    "title": "Portfolio Occupancy Rate",
                    "data_source": "tenancy_aggregator.get_occupancy_summary"
                },
                {
                    "id": "tenant_next_of_kin",
                    "type": "table",
                    "title": "Active Tenants & Emergency Contacts",
                    "data_source": "tenancy_aggregator.get_active_tenants_with_nok" # Placeholder for specific aggregator
                },
                {
                    "id": "maintenance_summary",
                    "type": "alert",
                    "title": "Open Maintenance Issues",
                    "data_source": "maintenance_aggregator.get_maintenance_summary"
                },
                {
                    "id": "agency_performance",
                    "type": "table",
                    "title": "Delegated Agency Performance",
                    "data_source": "property_aggregator.get_delegated_agency_metrics" # Placeholder
                }
            ],
            "data_blocks": {
                "financials": {
                    "total_revenue": financials.get("total_revenue", 0.0),
                    "outstanding_arrears": financials.get("outstanding_arrears", 0.0),
                    "collection_rate": financials.get("collection_rate", 0.0)
                },
                "occupancy": {
                    "occupancy_rate": occupancy.get("occupancy_rate", 0.0),
                    "occupied_units": occupancy.get("occupied_units", 0),
                    "vacant_units": occupancy.get("vacant_units", 0)
                },
                "maintenance": maintenance,
                "applications": applications
            }
        }