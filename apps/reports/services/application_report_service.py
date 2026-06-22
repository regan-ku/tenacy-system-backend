import logging
from django.db import transaction
from django.utils import timezone

from ..models import Report, ReportSnapshot
from ..aggregators import ApplicationAggregator
from ..exporters.excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)

class ApplicationReportService:
    """
    Handles the generation of Application Conversion & Pipeline Reports.
    """

    @staticmethod
    @transaction.atomic
    def initiate_application_report(user, title: str, parameters: dict) -> Report:
        """
        Creates a Report record and triggers background processing for application data.
        """
        report = Report.objects.create(
            title=title,
            report_type=Report.ReportType.APPLICATIONS,
            generated_by=user,
            parameters=parameters,
            status=Report.Status.PENDING
        )
        
        ApplicationReportService._process_report(report.id)
        return report

    @staticmethod
    def _process_report(report_id: int):
        """
        Core processing logic for the application report.
        """
        try:
            report = Report.objects.select_related('generated_by').get(id=report_id)
            report.status = Report.Status.PROCESSING
            report.save(update_fields=['status'])

            user = report.generated_by
            params = report.parameters
            days = params.get('days', 30)

            # 1. Aggregate Data
            pipeline_summary = ApplicationAggregator.get_application_pipeline_summary(user)
            application_trend = ApplicationAggregator.get_application_trend(user, days=days)

            snapshot_payload = {
                "generated_at": timezone.now().isoformat(),
                "period_days": days,
                "pipeline_summary": pipeline_summary,
                "application_trend": application_trend
            }

            # 2. Save Immutable Snapshot
            ReportSnapshot.objects.create(
                report=report,
                snapshot_data=snapshot_payload
            )

            # 3. Generate Export (Excel for detailed funnel analysis)
            filename = f"application_report_{report.id}_{timezone.now().strftime('%Y%m%d')}.xlsx"
            export_result = ExcelExporter.generate_excel_from_data(
                snapshot_payload,
                filename,
                sheet_name="Application Funnel"
            )

            if export_result["success"]:
                report.file_url = export_result["file_url"]
                report.status = Report.Status.COMPLETED
            else:
                report.status = Report.Status.FAILED
                report.error_message = export_result.get("error", "Excel generation failed")

            report.completed_at = timezone.now()
            report.save(update_fields=['status', 'file_url', 'error_message', 'completed_at'])

        except Exception as e:
            logger.error(f"Failed to process application report {report_id}: {str(e)}")
            Report.objects.filter(id=report_id).update(
                status=Report.Status.FAILED,
                error_message=str(e),
                completed_at=timezone.now()
            )