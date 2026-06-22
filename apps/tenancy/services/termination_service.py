from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import TenancyTermination, Tenancy, TenancyHistory
from ..services.occupancy_service import OccupancyService

class TerminationService:
    """
    Manages the formal termination of a tenancy.
    Ensures proper archival to history and releases the unit back to marketplace availability.
    """

    @staticmethod
    @transaction.atomic
    def execute_termination(termination_record: TenancyTermination, approved_by) -> Tenancy:
        """
        Executes a termination. 
        1. Archives current tenancy to history.
        2. Marks tenancy as terminated.
        3. Releases unit occupancy (syncs with marketplace).
        """
        tenancy = termination_record.tenancy

        if tenancy.status in [Tenancy.Status.TERMINATED, Tenancy.Status.TRANSFERRED, Tenancy.Status.EXPIRED]:
            raise ValidationError("This tenancy has already been closed.")

        # 1. Archive to Tenancy History before modifying the active record
        TenancyHistory.objects.create(
            tenant=tenancy.tenant,
            unit=tenancy.unit,
            property=tenancy.property,
            tenancy_type=tenancy.tenancy_type,
            start_date=tenancy.start_date,
            end_date=termination_record.effective_date,
            final_status='terminated',
            termination_reason=termination_record.notes or termination_record.get_termination_type_display(),
            manager_notes=f"Penalty applied: {termination_record.penalty_applied}" if termination_record.penalty_applied > 0 else ""
        )

        # 2. Update tenancy status
        tenancy.status = Tenancy.Status.TERMINATED
        tenancy.save(update_fields=['status'])

        # 3. Release unit occupancy (This triggers the Marketplace Sync to make the unit available again)
        OccupancyService.mark_unit_vacant(tenancy.unit, tenancy)

        # 4. Update termination record
        termination_record.approved_by = approved_by
        termination_record.save(update_fields=['approved_by'])

        return tenancy

    @staticmethod
    @transaction.atomic
    def process_natural_expiry(tenancy: Tenancy):
        """
        Automatically handles tenancies that have reached their end_date without extension or termination.
        Can be run as a daily Celery background task.
        """
        if tenancy.status in [Tenancy.Status.ACTIVE, Tenancy.Status.EXTENDED]:
            # Archive to history
            TenancyHistory.objects.create(
                tenant=tenancy.tenant,
                unit=tenancy.unit,
                property=tenancy.property,
                tenancy_type=tenancy.tenancy_type,
                start_date=tenancy.start_date,
                end_date=tenancy.end_date,
                final_status='expired',
                termination_reason="Natural lease expiry"
            )
            
            tenancy.status = Tenancy.Status.EXPIRED
            tenancy.save(update_fields=['status'])
            
            # Release unit
            OccupancyService.mark_unit_vacant(tenancy.unit, tenancy)