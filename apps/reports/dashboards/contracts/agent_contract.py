from .shared_blocks import SharedDashboardBlocks

class AgentDashboardContract:
    """
    Defines the data requirements for the Agent dashboard.
    Focuses on assigned properties, application pipeline, maintenance coordination, and tenant communication.
    """

    @staticmethod
    def get_contract_data(user):
        """
        Assembles the exact data payload required by the Agent dashboard UI.
        Automatically scoped to the properties delegated to this agent's parent agency.
        """
        return {
            "role": "agent",
            "required_widgets": [
                {
                    "id": "application_pipeline",
                    "type": "table",
                    "title": "Pending Applications",
                    "data_source": "application_aggregator.get_application_pipeline_summary"
                },
                {
                    "id": "maintenance_queue",
                    "type": "alert",
                    "title": "Open Maintenance Requests",
                    "data_source": "maintenance_aggregator.get_maintenance_summary"
                },
                {
                    "id": "occupancy_status",
                    "type": "chart",
                    "title": "Assigned Units Occupancy",
                    "data_source": "tenancy_aggregator.get_occupancy_summary"
                },
                {
                    "id": "tenant_communications",
                    "type": "list",
                    "title": "Recent Tenant Messages",
                    "data_source": "communication_aggregator.get_recent_messages"
                }
            ],
            "data_blocks": {
                "applications": SharedDashboardBlocks.get_application_pipeline(user),
                "maintenance": SharedDashboardBlocks.get_maintenance_alerts(user),
                "occupancy": SharedDashboardBlocks.get_occupancy_kpis(user)
            }
        }