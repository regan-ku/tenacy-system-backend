from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from ..models import TenancyWaiver, TenancyNote
from ..services.tenancy_service import TenancyService

class WaiverService:
    """
    Manages the approval workflow for financial waivers (deposit/service charge/rent).
    
    CRITICAL RULE: Only managers (landlord, agency, admin) can approve waivers.
    Agents and tenants CANNOT approve waivers - this is a manager-only decision.
    
    Automatically triggers tenancy activation if all financial conditions are met.
    """

    # Roles allowed to approve waivers
    MANAGER_ROLES = ['landlord', 'agency', 'admin', 'manager']

    @staticmethod
    def validate_manager_authority(user) -> None:
        """
        Ensures only managers can approve waivers.
        Raises PermissionDenied if user is not authorized.
        """
        if user.role not in WaiverService.MANAGER_ROLES:
            raise PermissionDenied(
                f"Only managers ({', '.join(WaiverService.MANAGER_ROLES)}) can approve waivers. "
                f"Your role '{user.role}' is not authorized."
            )

    @staticmethod
    @transaction.atomic
    def approve_waiver(waiver: TenancyWaiver, approved_by) -> TenancyWaiver:
        """
        Approves a waiver request and updates the parent tenancy's financial flags.
        
        ENFORCEMENT: Only managers can call this method.
        """
        # ✅ CRITICAL: Enforce manager-only approval
        WaiverService.validate_manager_authority(approved_by)
        
        if waiver.status != 'pending':
            raise ValidationError("Only pending waivers can be approved.")

        tenancy = waiver.tenancy

        # 1. Update waiver record
        waiver.status = 'approved'
        waiver.approved_by = approved_by
        waiver.processed_at = timezone.now()
        waiver.save(update_fields=['status', 'approved_by', 'processed_at'])

        # 2. Update tenancy financial flags based on waiver type
        update_fields = []
        if waiver.waiver_type in ['deposit', 'both']:
            tenancy.deposit_waived = True
            update_fields.append('deposit_waived')
            
        if waiver.waiver_type in ['service_charge', 'both']:
            tenancy.service_charge_waived = True
            update_fields.append('service_charge_waived')
            
        # Handle rent waiver (future use, but supported)
        if waiver.waiver_type == 'rent':
            if hasattr(tenancy, 'rent_waived'):
                tenancy.rent_waived = True
                update_fields.append('rent_waived')
            
        if update_fields:
            tenancy.save(update_fields=update_fields)

        # 3. Log the approval as a tenancy note for audit trail
        TenancyNote.objects.create(
            tenancy=tenancy,
            note_type='financial',
            content=f"Waiver approved by {approved_by.role} ({approved_by.email}). "
                    f"Type: {waiver.waiver_type}. Reason: {waiver.reason or 'Not specified'}",
            created_by=approved_by,
            is_confidential=False
        )

        # 4. Check if tenancy is now ready for activation
        if tenancy.status == 'pending_payment' and tenancy.is_ready_for_activation():
            TenancyService.activate_tenancy(tenancy, activated_by=approved_by)

        return waiver

    @staticmethod
    @transaction.atomic
    def reject_waiver(waiver: TenancyWaiver, approved_by, reason: str = "") -> TenancyWaiver:
        """
        Rejects a waiver request.
        
        ENFORCEMENT: Only managers can call this method.
        """
        # ✅ CRITICAL: Enforce manager-only rejection
        WaiverService.validate_manager_authority(approved_by)
        
        if waiver.status != 'pending':
            raise ValidationError("Only pending waivers can be rejected.")

        waiver.status = 'rejected'
        waiver.approved_by = approved_by
        waiver.processed_at = timezone.now()
        waiver.save(update_fields=['status', 'approved_by', 'processed_at'])
        
        # Log the rejection as a tenancy note
        TenancyNote.objects.create(
            tenancy=waiver.tenancy,
            note_type='financial',
            content=f"Waiver request rejected by {approved_by.role} ({approved_by.email}). "
                    f"Reason: {reason or 'Not specified'}",
            created_by=approved_by,
            is_confidential=False
        )

        return waiver

    @staticmethod
    @transaction.atomic
    def create_and_approve_waiver(
        tenancy,
        waiver_type: str,
        reason: str,
        manager_user
    ) -> TenancyWaiver:
        """
        Convenience method for managers to create and immediately approve a waiver.
        Used by the direct-manager flows (e.g., AgencyFinancialTab waiver buttons).
        
        This bypasses the request/approval cycle since the manager is both
        requesting and approving in one action.
        """
        # ✅ CRITICAL: Enforce manager-only authority
        WaiverService.validate_manager_authority(manager_user)
        
        if waiver_type not in ['deposit', 'service_charge', 'rent', 'both']:
            raise ValidationError(f"Invalid waiver type: {waiver_type}")
        
        # Create the waiver record
        waiver = TenancyWaiver.objects.create(
            tenancy=tenancy,
            waiver_type=waiver_type,
            reason=reason or "Manager-initiated waiver",
            requested_by=manager_user,
            approved_by=manager_user,
            status='approved',
            processed_at=timezone.now()
        )
        
        # Apply the waiver
        return WaiverService.approve_waiver(waiver, approved_by=manager_user)

    @staticmethod
    @transaction.atomic
    def revoke_waiver(waiver: TenancyWaiver, revoked_by, reason: str = "") -> TenancyWaiver:
        """
        Revokes a previously approved waiver.
        Resets the tenancy's financial flags and may deactivate the tenancy.
        
        ENFORCEMENT: Only managers can call this method.
        """
        # ✅ CRITICAL: Enforce manager-only authority
        WaiverService.validate_manager_authority(revoked_by)
        
        if waiver.status != 'approved':
            raise ValidationError("Only approved waivers can be revoked.")
        
        tenancy = waiver.tenancy
        
        # 1. Mark waiver as revoked
        waiver.status = 'revoked'
        waiver.processed_at = timezone.now()
        waiver.save(update_fields=['status', 'processed_at'])
        
        # 2. Reset tenancy financial flags
        update_fields = []
        if waiver.waiver_type in ['deposit', 'both']:
            tenancy.deposit_waived = False
            update_fields.append('deposit_waived')
            
        if waiver.waiver_type in ['service_charge', 'both']:
            tenancy.service_charge_waived = False
            update_fields.append('service_charge_waived')
            
        if waiver.waiver_type == 'rent':
            if hasattr(tenancy, 'rent_waived'):
                tenancy.rent_waived = False
                update_fields.append('rent_waived')
        
        if update_fields:
            tenancy.save(update_fields=update_fields)
        
        # 3. If tenancy was active and no longer meets activation criteria, suspend it
        if tenancy.status == 'active' and not tenancy.is_ready_for_activation():
            tenancy.status = 'suspended'
            tenancy.save(update_fields=['status'])
        
        # 4. Log the revocation
        TenancyNote.objects.create(
            tenancy=tenancy,
            note_type='financial',
            content=f"Waiver revoked by {revoked_by.role} ({revoked_by.email}). "
                    f"Type: {waiver.waiver_type}. Reason: {reason or 'Not specified'}",
            created_by=revoked_by,
            is_confidential=False
        )
        
        return waiver