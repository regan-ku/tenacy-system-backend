from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import TenancyWaiver
from ..services.tenancy_service import TenancyService

class WaiverService:
    """
    Manages the approval workflow for financial waivers (deposit/service charge).
    Automatically triggers tenancy activation if all financial conditions are met.
    """

    @staticmethod
    @transaction.atomic
    def approve_waiver(waiver: TenancyWaiver, approved_by) -> TenancyWaiver:
        """
        Approves a waiver request and updates the parent tenancy's financial flags.
        """
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
            
        if update_fields:
            tenancy.save(update_fields=update_fields)

        # 3. Check if tenancy is now ready for activation
        if tenancy.status == 'pending_payment' and tenancy.is_ready_for_activation():
            TenancyService.activate_tenancy(tenancy, activated_by=approved_by)

        return waiver

    @staticmethod
    @transaction.atomic
    def reject_waiver(waiver: TenancyWaiver, approved_by, reason: str = "") -> TenancyWaiver:
        """
        Rejects a waiver request.
        """
        if waiver.status != 'pending':
            raise ValidationError("Only pending waivers can be rejected.")

        waiver.status = 'rejected'
        waiver.approved_by = approved_by
        waiver.processed_at = timezone.now()
        waiver.save(update_fields=['status', 'approved_by', 'processed_at'])
        
        # Optional: Add a tenancy note about the rejection
        from ..models import TenancyNote
        TenancyNote.objects.create(
            tenancy=waiver.tenancy,
            note_type='financial',
            content=f"Waiver request rejected. Reason: {reason or 'Not specified'}",
            created_by=approved_by
        )

        return waiver