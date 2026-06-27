from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import TenancyExtension, Tenancy, TenancyNote

class ExtensionService:
    """
    Manages the workflow for extending a tenancy beyond its original end date.
    """

    @staticmethod
    @transaction.atomic
    def approve_extension(extension_request: TenancyExtension, approved_by) -> Tenancy:
        """
        Approves an extension request, updates the tenancy end date, 
        and adjusts rent if specified.
        """
        if extension_request.status != 'pending':
            raise ValidationError("Only pending extension requests can be approved.")

        tenancy = extension_request.tenancy

        # 1. Validate the new end date is actually in the future
        if extension_request.requested_new_end_date <= timezone.now().date():
            raise ValidationError("New end date must be in the future.")

        # 2. Update tenancy record
        update_fields = ['end_date']
        tenancy.end_date = extension_request.requested_new_end_date
        
        # Apply rent adjustment if proposed and approved
        if extension_request.proposed_rent_adjustment and extension_request.proposed_rent_adjustment != 0:
            tenancy.rent_amount += extension_request.proposed_rent_adjustment
            update_fields.append('rent_amount')
            
        # Update status to extended if it was previously active
        if tenancy.status == Tenancy.Status.ACTIVE:
            tenancy.status = Tenancy.Status.EXTENDED
            update_fields.append('status')
            
        tenancy.save(update_fields=update_fields)

        # 3. Update extension request status
        extension_request.status = 'approved'
        extension_request.approved_by = approved_by
        extension_request.processed_at = timezone.now()
        extension_request.save(update_fields=['status', 'approved_by', 'processed_at'])

        # 4. Log the extension as a tenancy note for audit trail
        TenancyNote.objects.create(
            tenancy=tenancy,
            note_type='general',
            content=f"Tenancy extended to {tenancy.end_date}. Rent adjusted by {extension_request.proposed_rent_adjustment or 0}.",
            created_by=approved_by
        )

        return tenancy

    @staticmethod
    @transaction.atomic
    def reject_extension(
        extension_request: TenancyExtension, 
        approved_by, 
        reason: str = ""
    ) -> TenancyExtension:
        """
        Rejects an extension request.
        """
        if extension_request.status != 'pending':
            raise ValidationError("Only pending extension requests can be rejected.")

        extension_request.status = 'rejected'
        extension_request.approved_by = approved_by
        extension_request.processed_at = timezone.now()
        extension_request.save(update_fields=['status', 'approved_by', 'processed_at'])

        # Log the rejection as a tenancy note
        TenancyNote.objects.create(
            tenancy=extension_request.tenancy,
            note_type='general',
            content=f"Extension request rejected. Reason: {reason or 'Not specified'}",
            created_by=approved_by
        )

        return extension_request

    @staticmethod
    @transaction.atomic
    def execute_direct_manager_extension(
        tenancy: Tenancy,
        new_end_date,
        reason: str,
        approved_by,
        rent_adjustment=0
    ) -> tuple[Tenancy, TenancyExtension]:
        """
        For paper-based or manager-initiated extensions that bypass the application system.
        Creates the TenancyExtension record internally and executes immediately.
        Ensures identical audit trail to application-based extensions.
        """
        # Validate the new end date is in the future
        if new_end_date <= timezone.now().date():
            raise ValidationError("New end date must be in the future.")
        
        # Create internal extension record for audit
        extension_record = TenancyExtension.objects.create(
            tenancy=tenancy,
            requested_new_end_date=new_end_date,
            proposed_rent_adjustment=rent_adjustment,
            reason=reason or "Manager-initiated extension",
            requested_by=approved_by,
            status='approved',  # Pre-approved
            approved_by=approved_by,
            processed_at=timezone.now()
        )
        
        # Execute using existing logic
        updated_tenancy = ExtensionService.approve_extension(
            extension_request=extension_record,
            approved_by=approved_by
        )
        
        return updated_tenancy, extension_record