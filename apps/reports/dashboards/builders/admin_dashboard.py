from ..contracts.admin_contract import AdminDashboardContract

class AdminDashboardBuilder:
    """
    Builds the dashboard payload specifically for the 'admin' role.
    Executes the AdminDashboardContract to assemble system-wide metrics.
    """

    @staticmethod
    def build(user):
        """
        Assembles the admin dashboard data by executing the contract.
        Provides a global view of platform health, revenue, and user metrics.
        """
        # 1. Execute the contract to get the required structure and data blocks
        contract_data = AdminDashboardContract.get_contract_data(user)
        
        # 2. Return the structured payload ready for the frontend
        return {
            "success": True,
            "role": contract_data["role"],
            "widgets": contract_data["required_widgets"],
            "data": contract_data["data_blocks"],
            "generated_at": __import__('django.utils.timezone').utils.timezone.now().isoformat()
        }