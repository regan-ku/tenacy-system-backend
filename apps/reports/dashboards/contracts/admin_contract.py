from .shared_blocks import SharedDashboardBlocks

class AdminDashboardContract:
    """
    Defines the data requirements for the System Administrator dashboard.
    Focuses on system-wide health, user verification queues, and macro-level analytics.
    """

    @staticmethod
    def get_contract_data(user):
        """
        Assembles the exact data payload required by the Admin dashboard UI.
        """
        # Admins get a global view, so we pass the user to let aggregators handle any 
        # specific scoping, though admins typically see everything.
        
        return {
            "role": "admin",
            "required_widgets": [
                {
                    "id": "system_health",
                    "type": "kpi_card",
                    "title": "System Health & Uptime",
                    "data_source": "system_monitoring.get_health_status" # Placeholder for future system aggregator
                },
                {
                    "id": "verification_queue",
                    "type": "alert",
                    "title": "Pending Verifications",
                    "data_source": "accounts_aggregator.get_pending_verifications" # Placeholder
                },
                {
                    "id": "global_financials",
                    "type": "chart",
                    "title": "Platform-Wide Revenue Trend",
                    "data_source": "payment_aggregator.get_financial_summary"
                },
                {
                    "id": "global_occupancy",
                    "type": "kpi_card",
                    "title": "Total Platform Occupancy",
                    "data_source": "tenancy_aggregator.get_occupancy_summary"
                },
                {
                    "id": "active_users",
                    "type": "table",
                    "title": "Recent User Registrations",
                    "data_source": "accounts_aggregator.get_recent_users" # Placeholder
                }
            ],
            "data_blocks": {
                "financials": SharedDashboardBlocks.get_financial_kpis(user),
                "occupancy": SharedDashboardBlocks.get_occupancy_kpis(user),
                # Admin-specific aggregators would be called here in a full implementation
            }
        }