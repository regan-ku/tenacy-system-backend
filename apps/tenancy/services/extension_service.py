from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import TenancyExtension, Tenancy
from ..utils.tenancy_utils import TenancyUtils

class ExtensionService:
    """
    Manages the workflow for extending a tenancy beyond its original end date.
    """

    @staticmethod
    @transaction.atomic
    def approve_extension(extension_request: TenancyExtension, approved_by) -> Tenancy:
        """
        Approves an extension request, updates the tenancy end date, and adjusts rent if specified.
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
        if extension_request.proposed_rent_adjustment > 0:
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

        # 4. Log the extension
        from ..models import TenancyNote
        TenancyNote.objects.create(
            tenancy=tenancy,
            note_type='general',
            content=f"Tenancy extended to {tenancy.end_date}. Rent adjusted by {extension_request.proposed_rent_adjustment}.",
            created_by=approved_by
        )

        return tenancy

    @staticmethod
    @transaction.atomic
    def reject_extension(extension_request: TenancyExtension, approved_by, reason: str = "") -> TenancyExtension:
        """
        Rejects an extension request.
        """
        if extension_request.status != 'pending':
            raise ValidationError("Only pending extension requests can be rejected.")

        extension_request.status = 'rejected'
        extension_request.approved_by = approved_by
        extension_request.processed_at = timezone.now()
        extension_request.save(update_fields=['status', 'approved_by', 'processed_at'])

        return extension_request