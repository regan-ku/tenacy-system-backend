from .shared_blocks import SharedDashboardBlocks
from apps.accounts.models import NextOfKin  # Adjust import based on actual accounts app structure

class TenantDashboardContract:
    """
    Defines the data requirements for the Tenant dashboard.
    Focuses on personal profile, Next of Kin, active/past/transferred tenancies, 
    and personal financials.
    """

    @staticmethod
    def get_contract_data(user):
        """
        Assembles the exact data payload required by the Tenant dashboard UI.
        Strictly scoped to the specific tenant's records.
        """
        # CRITICAL: Fetch Next of Kin (visible to tenant, landlord, and agency)
        next_of_kin = NextOfKin.objects.filter(user=user).first()
        nok_data = {
            "name": next_of_kin.full_name if next_of_kin else "",
            "relationship": next_of_kin.relationship if next_of_kin else "",
            "phone": next_of_kin.phone_number if next_of_kin else "",
            "city": next_of_kin.city if next_of_kin else ""
        } if next_of_kin else None

        # Tenants CAN use shared blocks for scoped data (e.g., their own maintenance alerts)
        maintenance_alerts = SharedDashboardBlocks.get_maintenance_alerts(user)

        return {
            "role": "tenant",
            "required_widgets": [
                {
                    "id": "active_tenancies",
                    "type": "table",
                    "title": "My Active Tenancies",
                    "data_source": "tenancy_aggregator.get_tenant_active_tenancies"
                },
                {
                    "id": "financial_summary",
                    "type": "kpi_card",
                    "title": "Outstanding Balance & Next Due Date",
                    "data_source": "payment_aggregator.get_tenant_balance"
                },
                {
                    "id": "maintenance_requests",
                    "type": "list",
                    "title": "My Maintenance Requests",
                    "data_source": "maintenance_aggregator.get_tenant_requests"
                },
                {
                    "id": "upcoming_payments",
                    "type": "alert",
                    "title": "Upcoming Rent Due Dates",
                    "data_source": "payment_aggregator.get_upcoming_invoices"
                }
            ],
            "data_blocks": {
                "profile": {
                    "name": user.get_full_name(),
                    "email": user.email,
                    "phone": user.phone_number,
                    "next_of_kin": nok_data  # CRITICAL: Must be visible to tenant
                },
                "tenancies": {
                    "active": [],      # Populated by tenancy_aggregator.get_active_tenancies(user)
                    "past": [],        # Populated by tenancy_aggregator.get_historical_tenancies(user)
                    "transferred": []  # Populated by tenancy_aggregator.get_transferred_tenancies(user)
                },
                "financials": {
                    "current_due": 0.0,
                    "total_arrears": 0.0,
                    "payment_history": []
                },
                "operations": {
                    "open_maintenance": maintenance_alerts.get("open_requests", 0),
                    "pending_applications": 0
                }
            }
        }