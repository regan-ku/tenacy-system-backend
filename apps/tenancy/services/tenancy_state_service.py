from django.utils import timezone
from ..models import Tenancy
from ..utils.tenancy_utils import TenancyUtils

class TenancyStateService:
    """
    Evaluates the current state of a tenancy to determine valid next actions.
    Used to dynamically render frontend dashboard buttons (e.g., "Extend", "Terminate", "Pay Deposit").
    """

    @staticmethod
    def get_available_actions(tenancy: Tenancy, user) -> list:
        """
        Returns a list of string actions the current user is allowed to perform on this tenancy.
        """
        actions = []
        status = tenancy.status

        # 1. Financial Actions (Pending Payment)
        if status == Tenancy.Status.PENDING_PAYMENT:
            actions.append('mark_deposit_paid')
            actions.append('mark_service_charge_paid')
            actions.append('request_waiver')
            
            # Check if ready to activate
            if tenancy.is_ready_for_activation():
                actions.append('activate_tenancy')

        # 2. Lifecycle Actions (Active or Extended)
        elif status in [Tenancy.Status.ACTIVE, Tenancy.Status.EXTENDED]:
            # Check if expiring soon (e.g., within 60 days)
            if tenancy.end_date and TenancyUtils.is_expiring_soon(tenancy.end_date, days_threshold=60):
                actions.append('request_extension')
                
            actions.append('request_transfer')
            actions.append('initiate_termination')
            actions.append('add_note')

        # 3. Suspended State
        elif status == Tenancy.Status.SUSPENDED:
            actions.append('reinstate_tenancy')
            actions.append('initiate_termination')

        return actions

    @staticmethod
    def get_tenancy_health_status(tenancy: Tenancy) -> dict:
        """
        Returns a health check object for the tenancy, useful for dashboard alerts.
        """
        alerts = []
        
        if tenancy.status == Tenancy.Status.PENDING_PAYMENT:
            alerts.append({"type": "warning", "message": "Tenancy is pending financial settlement."})
            
        if tenancy.end_date and TenancyUtils.is_expiring_soon(tenancy.end_date, days_threshold=30):
            days_left = TenancyUtils.get_days_remaining(tenancy.end_date)
            alerts.append({"type": "urgent", "message": f"Tenancy expires in {days_left} days."})
            
        # Check for pending waivers or extensions
        has_pending_waiver = tenancy.waivers.filter(status='pending').exists()
        has_pending_extension = tenancy.extensions.filter(status='pending').exists()
        
        if has_pending_waiver:
            alerts.append({"type": "info", "message": "Financial waiver request is pending approval."})
        if has_pending_extension:
            alerts.append({"type": "info", "message": "Extension request is pending approval."})

        return {
            "status": tenancy.status,
            "days_remaining": TenancyUtils.get_days_remaining(tenancy.end_date) if tenancy.end_date else None,
            "alerts": alerts
        }