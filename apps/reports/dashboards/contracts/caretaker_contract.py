from .shared_blocks import SharedDashboardBlocks

class CaretakerDashboardContract:
    """
    Defines the data requirements for the Caretaker dashboard.
    Focuses on field operations: assigned maintenance tasks, inspections, urgent alerts, and property condition tracking.
    """

    @staticmethod
    def get_contract_data(user):
        """
        Assembles the exact data payload required by the Caretaker dashboard UI.
        Strictly scoped to the specific buildings/units assigned to this caretaker.
        """
        return {
            "role": "caretaker",
            "required_widgets": [
                {
                    "id": "open_tasks",
                    "type": "table",
                    "title": "My Open Maintenance Tasks",
                    "data_source": "maintenance_aggregator.get_assigned_tasks"
                },
                {
                    "id": "urgent_alerts",
                    "type": "alert",
                    "title": "Urgent/Overdue Requests",
                    "data_source": "maintenance_aggregator.get_urgent_alerts"
                },
                {
                    "id": "inspection_schedule",
                    "type": "list",
                    "title": "Upcoming Inspections",
                    "data_source": "maintenance_aggregator.get_inspection_schedule"
                },
                {
                    "id": "assigned_units",
                    "type": "kpi_card",
                    "title": "Units Under My Care",
                    "data_source": "property_aggregator.get_assigned_units_count"
                },
                {
                    "id": "reporting_status",
                    "type": "chart",
                    "title": "Task Completion Rate",
                    "data_source": "maintenance_aggregator.get_completion_metrics"
                }
            ],
            "data_blocks": {
                "tasks": SharedDashboardBlocks.get_maintenance_alerts(user),
                "assigned_properties": [], # Populated by property_aggregator with caretaker filter
                "urgent_count": 0
            }
        }