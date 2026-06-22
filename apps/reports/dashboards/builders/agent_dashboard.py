from ..contracts.agent_contract import AgentDashboardContract
from django.utils import timezone

class AgentDashboardBuilder:
    """
    Builds the dashboard payload specifically for the 'agent' role.
    Executes the AgentDashboardContract to assemble the required data blocks.
    """

    @staticmethod
    def build(user):
        """
        Assembles the agent dashboard data by executing the contract.
        Automatically scoped to the properties delegated to this agent's parent agency.
        """
        contract_data = AgentDashboardContract.get_contract_data(user)
        
        return {
            "success": True,
            "role": contract_data["role"],
            "widgets": contract_data["required_widgets"],
            "data": contract_data["data_blocks"],
            "generated_at": timezone.now().isoformat()
        }