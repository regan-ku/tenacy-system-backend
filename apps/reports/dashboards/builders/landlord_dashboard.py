from ..contracts.landlord_contract import LandlordDashboardContract

class LandlordDashboardBuilder:
    """
    Builds the dashboard payload specifically for the 'landlord' role.
    Executes the LandlordDashboardContract to assemble the required data blocks.
    """

    @staticmethod
    def build(user):
        """
        Assembles the landlord dashboard data by executing the contract.
        Landlords care most about: Revenue, Occupancy, Tenant Next of Kin, and Portfolio Overview.
        """
        # 1. Execute the contract to get the required structure and data blocks
        contract_data = LandlordDashboardContract.get_contract_data(user)
        
        # 2. The contract already pre-fetches the scoped data blocks. 
        # We simply return the contract's structured payload, which is ready for the frontend.
        return {
            "success": True,
            "role": contract_data["role"],
            "widgets": contract_data["required_widgets"],
            "data": contract_data["data_blocks"],
            "generated_at": __import__('django.utils.timezone').utils.timezone.now().isoformat()
        }