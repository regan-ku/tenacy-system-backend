from ..contracts.agency_contract import AgencyDashboardContract
from django.utils import timezone

class AgencyDashboardBuilder:
    """
    Builds the dashboard payload specifically for the 'agency' role.
    Executes the AgencyDashboardContract to assemble the required data blocks.
    """

    @staticmethod
    def build(user):
        """
        Assembles the agency dashboard data by executing the contract.
        Automatically scoped to the properties delegated to this agency.
        """
        contract_data = AgencyDashboardContract.get_contract_data(user)
        
        return {
            "success": True,
            "role": contract_data["role"],
            "widgets": contract_data["required_widgets"],
            "data": contract_data["data_blocks"],
            "generated_at": timezone.now().isoformat()
        }