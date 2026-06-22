from ..contracts.tenant_contract import TenantDashboardContract

class TenantDashboardBuilder:
    """
    Builds the dashboard payload specifically for the 'tenant' role.
    Executes the TenantDashboardContract to assemble personal profile, tenancies, and financials.
    """

    @staticmethod
    def build(user):
        """
        Assembles the tenant dashboard data by executing the contract.
        Ensures Next of Kin and multiple active tenancies are correctly structured.
        """
        # 1. Execute the contract to get the required structure and data blocks
        contract_data = TenantDashboardContract.get_contract_data(user)
        
        # 2. Return the structured payload ready for the frontend
        return {
            "success": True,
            "role": contract_data["role"],
            "widgets": contract_data["required_widgets"],
            "data": contract_data["data_blocks"],
            "generated_at": __import__('django.utils.timezone').utils.timezone.now().isoformat()
        }