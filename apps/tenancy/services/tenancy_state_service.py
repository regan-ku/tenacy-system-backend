from django.utils import timezone
from ..models import Tenancy, TenancyTransfer, TenancyExtension, TenancyTermination
from ..utils.tenancy_utils import TenancyUtils

class TenancyStateService:
    """
    Evaluates the current state of a tenancy to determine valid next actions.
    Used to dynamically render frontend dashboard buttons.
    
    ENHANCED FEATURES:
    - Role-based action filtering (tenant vs manager vs landlord)
    - Checks for existing pending requests
    - Supports direct-manager workflows
    - Manager-only waiver controls
    - Comprehensive health status with multi-domain alerts
    """

    @staticmethod
    def get_available_actions(tenancy: Tenancy, user) -> list:
        """
        Returns a list of string actions the current user is allowed to perform on this tenancy.
        Actions are filtered based on:
        1. Tenancy status
        2. User role and permissions
        3. Existing pending requests
        4. Business rules
        """
        actions = []
        status = tenancy.status
        user_role = user.role
        
        # Determine if user is a manager (landlord, agency, admin, manager)
        is_manager = user_role in ['landlord', 'agency', 'admin', 'manager']
        is_tenant = user_role == 'tenant'
        is_agent = user_role == 'agent'
        
        # Check for existing pending requests
        has_pending_transfer = TenancyTransfer.objects.filter(
            tenant=tenancy.tenant,
            from_unit=tenancy.unit,
            transfer_status='pending'
        ).exists()
        
        has_pending_extension = TenancyExtension.objects.filter(
            tenancy=tenancy,
            status='pending'
        ).exists()
        
        has_pending_termination = hasattr(tenancy, 'termination_record') or \
            TenancyTermination.objects.filter(tenancy=tenancy).exists()

        # ========================================
        # 1. PENDING PAYMENT STATE
        # ========================================
        if status == Tenancy.Status.PENDING_PAYMENT:
            # Tenant actions
            if is_tenant:
                actions.append('view_payment_details')
                actions.append('pay_deposit')
                actions.append('pay_service_charge')
                actions.append('view_tenancy_details')
            
            # Manager actions (waiver control - MANAGER ONLY)
            if is_manager:
                actions.append('apply_waiver')
                actions.append('view_waivers')
                if tenancy.deposit_waived or tenancy.service_charge_waived:
                    actions.append('revoke_waiver')
                actions.append('activate_tenancy_direct')  # Manager can force activate
                actions.append('add_note')
                actions.append('view_tenant_profile')
            
            # Check if ready to activate
            if tenancy.is_ready_for_activation():
                actions.append('activate_tenancy')

        # ========================================
        # 2. ACTIVE OR EXTENDED STATE
        # ========================================
        elif status in [Tenancy.Status.ACTIVE, Tenancy.Status.EXTENDED]:
            # Common actions for all users
            actions.append('view_tenancy_details')
            actions.append('view_payment_history')
            
            # Tenant-specific actions
            if is_tenant:
                actions.append('view_invoices')
                actions.append('make_payment')
                actions.append('submit_maintenance_request')
                actions.append('view_lease_agreement')
                
                # Request actions (only if no pending request exists)
                if not has_pending_transfer:
                    actions.append('request_transfer')
                if not has_pending_extension:
                    # Check if expiring soon
                    if tenancy.end_date and TenancyUtils.is_expiring_soon(tenancy.end_date, days_threshold=90):
                        actions.append('request_extension')
                if not has_pending_termination:
                    actions.append('initiate_termination')
                
                actions.append('add_note')
                actions.append('view_maintenance_requests')
            
            # Manager-specific actions (enhanced with direct workflows)
            if is_manager:
                actions.append('view_tenant_profile')
                actions.append('view_financial_summary')
                actions.append('add_note')
                actions.append('view_maintenance_requests')
                
                # Direct manager workflows (bypass application system)
                if not has_pending_transfer:
                    actions.append('direct_transfer')  # Manager-initiated transfer
                if not has_pending_extension:
                    actions.append('direct_extension')  # Manager-initiated extension
                if not has_pending_termination:
                    actions.append('direct_termination')  # Manager-initiated termination
                
                # Waiver management
                actions.append('view_waivers')
                actions.append('apply_waiver')
                if tenancy.deposit_waived or tenancy.service_charge_waived:
                    actions.append('revoke_waiver')
                
                # Tenancy management
                actions.append('suspend_tenancy')
                actions.append('generate_report')
                
                # Extension approval (if pending)
                if has_pending_extension:
                    actions.append('approve_extension')
                    actions.append('reject_extension')
            
            # Agent actions (limited based on delegation)
            if is_agent:
                actions.append('view_tenant_profile')
                actions.append('add_note')
                if not has_pending_transfer:
                    actions.append('request_transfer')
                if not has_pending_extension and tenancy.end_date and TenancyUtils.is_expiring_soon(tenancy.end_date, days_threshold=90):
                    actions.append('request_extension')

        # ========================================
        # 3. SUSPENDED STATE
        # ========================================
        elif status == Tenancy.Status.SUSPENDED:
            actions.append('view_tenancy_details')
            
            if is_manager:
                actions.append('reinstate_tenancy')
                actions.append('direct_termination')
                actions.append('view_tenant_profile')
                actions.append('view_financial_summary')
                actions.append('add_note')
            
            if is_tenant:
                actions.append('view_payment_history')
                actions.append('contact_support')

        # ========================================
        # 4. TERMINAL STATES (no actions allowed)
        # ========================================
        elif status in [Tenancy.Status.TERMINATED, Tenancy.Status.TRANSFERRED, Tenancy.Status.EXPIRED]:
            actions.append('view_tenancy_details')
            actions.append('view_tenancy_history')
            
            if is_manager:
                actions.append('view_tenant_profile')
                actions.append('generate_report')

        # ========================================
        # 5. PENDING PAYMENT WITH EXPIRATION RISK
        # ========================================
        if status == Tenancy.Status.PENDING_PAYMENT:
            # Check if tenancy is about to expire (3-hour recall rule)
            if hasattr(tenancy, 'expires_at') and tenancy.expires_at:
                hours_remaining = (tenancy.expires_at - timezone.now()).total_seconds() / 3600
                if hours_remaining < 1:
                    actions.append('urgent_payment_required')

        return actions

    @staticmethod
    def get_tenancy_health_status(tenancy: Tenancy) -> dict:
        """
        Returns a comprehensive health check object for the tenancy.
        Includes alerts from multiple domains:
        - Financial (payments, waivers, arrears)
        - Lifecycle (expiry, extensions, transfers)
        - Operational (maintenance, communications)
        - Compliance (documents, verification)
        """
        alerts = []
        health_score = 100  # Start with perfect health
        
        # ========================================
        # FINANCIAL ALERTS
        # ========================================
        if tenancy.status == Tenancy.Status.PENDING_PAYMENT:
            alerts.append({
                "type": "warning",
                "category": "financial",
                "message": "Tenancy is pending financial settlement.",
                "priority": "high"
            })
            health_score -= 20
            
            # Check expiration risk
            if hasattr(tenancy, 'expires_at') and tenancy.expires_at:
                hours_remaining = (tenancy.expires_at - timezone.now()).total_seconds() / 3600
                if hours_remaining < 1:
                    alerts.append({
                        "type": "urgent",
                        "category": "financial",
                        "message": f"Payment deadline in {int(hours_remaining * 60)} minutes!",
                        "priority": "critical"
                    })
                    health_score -= 30
        
        # Check for pending waivers
        has_pending_waiver = tenancy.waivers.filter(status='pending').exists()
        if has_pending_waiver:
            alerts.append({
                "type": "info",
                "category": "financial",
                "message": "Financial waiver request is pending approval.",
                "priority": "medium"
            })
            health_score -= 5
        
        # Check for revoked waivers (indicates financial instability)
        has_revoked_waiver = tenancy.waivers.filter(status='revoked').exists()
        if has_revoked_waiver:
            alerts.append({
                "type": "warning",
                "category": "financial",
                "message": "Previous waiver was revoked. Financial review recommended.",
                "priority": "medium"
            })
            health_score -= 10

        # ========================================
        # LIFECYCLE ALERTS
        # ========================================
        # Expiry warning
        if tenancy.end_date and TenancyUtils.is_expiring_soon(tenancy.end_date, days_threshold=30):
            days_left = TenancyUtils.get_days_remaining(tenancy.end_date)
            alerts.append({
                "type": "urgent" if days_left < 7 else "warning",
                "category": "lifecycle",
                "message": f"Tenancy expires in {days_left} days.",
                "priority": "high" if days_left < 7 else "medium"
            })
            health_score -= 15 if days_left < 7 else 5
        
        # Check for pending extension
        has_pending_extension = tenancy.extensions.filter(status='pending').exists()
        if has_pending_extension:
            alerts.append({
                "type": "info",
                "category": "lifecycle",
                "message": "Extension request is pending approval.",
                "priority": "medium"
            })
        
        # Check for pending transfer
        has_pending_transfer = TenancyTransfer.objects.filter(
            tenant=tenancy.tenant,
            from_unit=tenancy.unit,
            transfer_status='pending'
        ).exists()
        if has_pending_transfer:
            alerts.append({
                "type": "info",
                "category": "lifecycle",
                "message": "Transfer request is pending approval.",
                "priority": "medium"
            })
        
        # Check for pending termination
        has_pending_termination = hasattr(tenancy, 'termination_record')
        if has_pending_termination:
            alerts.append({
                "type": "warning",
                "category": "lifecycle",
                "message": "Termination request is pending review.",
                "priority": "high"
            })
            health_score -= 10

        # ========================================
        # OPERATIONAL ALERTS
        # ========================================
        # Check for open maintenance requests
        try:
            from apps.maintenance.models import MaintenanceRequest
            open_maintenance = MaintenanceRequest.objects.filter(
                unit=tenancy.unit,
                status__in=['open', 'assigned', 'in_progress']
            ).count()
            
            if open_maintenance > 0:
                alerts.append({
                    "type": "warning" if open_maintenance > 2 else "info",
                    "category": "operational",
                    "message": f"{open_maintenance} open maintenance request(s).",
                    "priority": "medium"
                })
                health_score -= 5 * open_maintenance
        except Exception:
            pass  # Maintenance app may not be fully integrated yet

        # ========================================
        # COMPLIANCE ALERTS
        # ========================================
        # Check if tenancy agreement is signed
        if hasattr(tenancy, 'agreement'):
            if not tenancy.agreement or tenancy.agreement.status != 'signed':
                alerts.append({
                    "type": "warning",
                    "category": "compliance",
                    "message": "Tenancy agreement is not signed.",
                    "priority": "high"
                })
                health_score -= 15

        # ========================================
        # HEALTH SCORE CALCULATION
        # ========================================
        health_score = max(0, health_score)  # Ensure non-negative
        
        # Determine health status
        if health_score >= 80:
            health_status = "excellent"
        elif health_score >= 60:
            health_status = "good"
        elif health_score >= 40:
            health_status = "fair"
        else:
            health_status = "poor"

        return {
            "status": tenancy.status,
            "health_score": health_score,
            "health_status": health_status,
            "days_remaining": TenancyUtils.get_days_remaining(tenancy.end_date) if tenancy.end_date else None,
            "alerts": alerts,
            "alert_summary": {
                "critical": len([a for a in alerts if a.get('priority') == 'critical']),
                "high": len([a for a in alerts if a.get('priority') == 'high']),
                "medium": len([a for a in alerts if a.get('priority') == 'medium']),
                "low": len([a for a in alerts if a.get('priority') == 'low'])
            }
        }

    @staticmethod
    def get_tenancy_summary(tenancy: Tenancy) -> dict:
        """
        Returns a quick summary of tenancy state for dashboard cards.
        Lightweight version without detailed alerts.
        """
        return {
            "status": tenancy.status,
            "status_display": tenancy.get_status_display(),
            "tenant_name": tenancy.tenant.get_full_name() or tenancy.tenant.email,
            "unit_code": tenancy.unit.unit_code,
            "property_name": tenancy.property.title,
            "rent_amount": float(tenancy.rent_amount),
            "start_date": str(tenancy.start_date),
            "end_date": str(tenancy.end_date) if tenancy.end_date else None,
            "days_remaining": TenancyUtils.get_days_remaining(tenancy.end_date) if tenancy.end_date else None,
            "is_expiring_soon": tenancy.end_date and TenancyUtils.is_expiring_soon(tenancy.end_date, days_threshold=30),
            "financial_status": {
                "deposit_paid": tenancy.deposit_paid,
                "deposit_waived": tenancy.deposit_waived,
                "service_charge_paid": tenancy.service_charge_paid,
                "service_charge_waived": tenancy.service_charge_waived,
                "is_ready_for_activation": tenancy.is_ready_for_activation()
            }
        }