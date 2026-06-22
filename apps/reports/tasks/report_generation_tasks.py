from celery import shared_task
import logging
from django.utils import timezone

from ..models import Report
from ..services import (
    FinancialReportService,
    OccupancyReportService,
    TenancyReportService,
    MaintenanceReportService,
    ApplicationReportService,
    PropertyReportService,
    MarketplaceReportService,
    CommunicationReportService
)

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_report_task(self, report_id: int):
    """
    Asynchronously processes a pending report generation request.
    Routes the request to the appropriate service based on report_type.
    """
    try:
        # Fetch the report record
        report = Report.objects.select_related('generated_by').get(id=report_id)
        
        if report.status != Report.Status.PENDING:
            logger.warning(f"Report {report_id} is no longer pending (status: {report.status}). Skipping.")
            return {"status": "skipped", "report_id": report_id}

        # Route to the correct service's internal processing method
        service_map = {
            'financial': FinancialReportService._process_report,
            'occupancy': OccupancyReportService._process_report,
            'tenancy': TenancyReportService._process_report,
            'maintenance': MaintenanceReportService._process_report,
            'applications': ApplicationReportService._process_report,
            'property': PropertyReportService._process_report,
            'marketplace': MarketplaceReportService._process_report,
            'communications': CommunicationReportService._process_report,
        }

        process_func = service_map.get(report.report_type)
        if not process_func:
            raise ValueError(f"Unsupported report type for async processing: {report.report_type}")

        # Execute the processing logic
        process_func(report_id)
        
        # Refresh and return final status
        report.refresh_from_db()
        return {"status": report.status, "report_id": report_id, "file_url": report.file_url}

    except Report.DoesNotExist:
        logger.error(f"Report {report_id} not found.")
        return {"status": "failed", "error": "Report not found"}
    except Exception as e:
        logger.error(f"Failed to generate report {report_id}: {str(e)}")
        # Update status to FAILED if the task completely crashes
        Report.objects.filter(id=report_id).update(
            status=Report.Status.FAILED,
            error_message=str(e),
            completed_at=timezone.now()
        )
        raise self.retry(exc=e, countdown=300) # Retry after 5 minutes