from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

# ... (Keep your existing recall_unpaid_approved_applications task here) ...

@shared_task
def expire_unpaid_transfers():
    """
    BUSINESS RULE: Transfers expire on the date of move-in if payments haven't been done.
    Checks for transfer tenancies that are still pending_payment 
    and whose move_in_date (start_date) has passed.
    """
    from apps.tenancy.models import Tenancy
    from apps.applications.models import Application

    today = timezone.now().date()
    
    # Find pending transfer tenancies where move-in date has passed
    unpaid_transfers = Tenancy.objects.filter(
        tenancy_type='transfer',
        status='pending_payment',
        start_date__lt=today
    ).select_related('tenant', 'unit')
    
    expired_count = 0
    for tenancy in unpaid_transfers:
        try:
            with transaction.atomic():
                # 1. Cancel the pending tenancy for the new unit
                tenancy.status = 'cancelled'
                tenancy.save(update_fields=['status'])
                
                # 2. Expire the linked application
                application = Application.objects.filter(
                    applicant=tenancy.tenant,
                    application_type='transfer',
                    status='approved'
                ).first()
                
                if application:
                    application.status = 'expired'
                    application.save(update_fields=['status'])
                    
                logger.info(f"Expired unpaid transfer for tenant {tenancy.tenant.email}")
                expired_count += 1
        except Exception as e:
            logger.error(f"Failed to expire transfer tenancy {tenancy.id}: {e}")
            
    return {"expired": expired_count}


@shared_task
def auto_vacate_terminated_units():
    """
    BUSINESS RULE: Unit becomes automatically vacant on the day/date of move out.
    Checks for tenancies scheduled for termination where the end_date has arrived.
    """
    from apps.tenancy.models import Tenancy, TenancyHistory
    from apps.tenancy.services.occupancy_service import OccupancyService

    today = timezone.now().date()
    
    scheduled_terminations = Tenancy.objects.filter(
        status='scheduled_for_termination',
        end_date__lte=today
    ).select_related('tenant', 'unit', 'property')
    
    vacated_count = 0
    for tenancy in scheduled_terminations:
        try:
            with transaction.atomic():
                # 1. Archive to history
                TenancyHistory.objects.create(
                    tenant=tenancy.tenant,
                    unit=tenancy.unit,
                    property=tenancy.property,
                    tenancy_type=tenancy.tenancy_type,
                    start_date=tenancy.start_date,
                    end_date=tenancy.end_date,
                    final_status='terminated',
                    termination_reason="Automated move-out date reached"
                )
                
                # 2. Update tenancy status
                tenancy.status = 'terminated'
                tenancy.save(update_fields=['status'])
                
                # 3. Release unit back to the marketplace
                OccupancyService.mark_unit_vacant(tenancy.unit, tenancy)
                
                logger.info(f"Auto-vacated unit {tenancy.unit.unit_code} for tenant {tenancy.tenant.email}")
                vacated_count += 1
        except Exception as e:
            logger.error(f"Failed to auto-vacate tenancy {tenancy.id}: {e}")
            
    return {"vacated": vacated_count}