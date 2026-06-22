from ..contracts.caretaker_contract import CaretakerDashboardContract
from django.utils import timezone

class CaretakerDashboardBuilder:
    """
    Builds the dashboard payload specifically for the 'caretaker' role.
    Executes the CaretakerDashboardContract to assemble the required data blocks.
    """

    @staticmethod
    def build(user):
        """
        Assembles the caretaker dashboard data by executing the contract.
        Strictly scoped to the specific buildings/units assigned to this caretaker.
        """
        contract_data = CaretakerDashboardContract.get_contract_data(user)
        
        return {
            "success": True,
            "role": contract_data["role"],
            "widgets": contract_data["required_widgets"],
            "data": contract_data["data_blocks"],
            "generated_at": timezone.now().isoformat()
        }