import logging
from django.db import transaction
from django.utils import timezone

from ..models import Report, ReportSnapshot
from ..aggregators import MaintenanceAggregator
from ..exporters.pdf_exporter import PDFExporter

logger = logging.getLogger(__name__)

class MaintenanceReportService:
    """
    Handles the generation of Maintenance & SLA Reports.
    """

    @staticmethod
    @transaction.atomic
    def initiate_maintenance_report(user, title: str, parameters: dict) -> Report:
        """
        Creates a Report record and triggers background processing for maintenance data.
        """
        report = Report.objects.create(
            title=title,
            report_type=Report.ReportType.MAINTENANCE,
            generated_by=user,
            parameters=parameters,
            status=Report.Status.PENDING
        )
        
        MaintenanceReportService._process_report(report.id)
        return report

    @staticmethod
    def _process_report(report_id: int):
        """
        Core processing logic for the maintenance report.
        """
        try:
            report = Report.objects.select_related('generated_by').get(id=report_id)
            report.status = Report.Status.PROCESSING
            report.save(update_fields=['status'])

            user = report.generated_by
            params = report.parameters
            days = params.get('days', 30)

            # 1. Aggregate Data
            maintenance_summary = MaintenanceAggregator.get_maintenance_summary(user)
            avg_resolution_time = MaintenanceAggregator.get_average_resolution_time(user, days=days)
            requests_by_category = MaintenanceAggregator.get_requests_by_category(user)

            snapshot_payload = {
                "generated_at": timezone.now().isoformat(),
                "period_days": days,
                "maintenance_summary": maintenance_summary,
                "avg_resolution_time": avg_resolution_time,
                "requests_by_category": requests_by_category
            }

            # 2. Save Immutable Snapshot
            ReportSnapshot.objects.create(
                report=report,
                snapshot_data=snapshot_payload
            )

            # 3. Generate Export (PDF for formal operational reporting)
            filename = f"maintenance_report_{report.id}_{timezone.now().strftime('%Y%m%d')}.pdf"
            export_result = PDFExporter.generate_pdf_from_template(
                "reports/maintenance_report.html",
                {"data": snapshot_payload, "user": user.email},
                filename
            )

            if export_result["success"]:
                report.file_url = export_result["file_url"]
                report.status = Report.Status.COMPLETED
            else:
                report.status = Report.Status.FAILED
                report.error_message = export_result.get("error", "PDF generation failed")

            report.completed_at = timezone.now()
            report.save(update_fields=['status', 'file_url', 'error_message', 'completed_at'])

        except Exception as e:
            logger.error(f"Failed to process maintenance report {report_id}: {str(e)}")
            Report.objects.filter(id=report_id).update(
                status=Report.Status.FAILED,
                error_message=str(e),
                completed_at=timezone.now()
            )