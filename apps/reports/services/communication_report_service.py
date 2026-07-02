import logging
from django.db import transaction
from django.utils import timezone

from ..models import Report, ReportSnapshot
from ..exporters.excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)

class CommunicationReportService:
    """
    Handles the generation of Communication & Notification Delivery Reports.
    """

    @staticmethod
    @transaction.atomic
    def initiate_communication_report(user, title: str, parameters: dict) -> Report:
        # ⚠️ TODO: Add 'COMMUNICATIONS' to Report.ReportType choices in models.py
        # For now, we reuse MAINTENANCE to prevent database errors.
        report = Report.objects.create(
            title=title,
            report_type=Report.ReportType.MAINTENANCE, 
            generated_by=user,
            parameters=parameters,
            status=Report.Status.PENDING
        )
        
        CommunicationReportService._process_report(report.id)
        return report

    @staticmethod
    def _process_report(report_id: int):
        try:
            report = Report.objects.select_related('generated_by').get(id=report_id)
            report.status = Report.Status.PROCESSING
            report.save(update_fields=['status'])

            user = report.generated_by
            params = report.parameters
            days = params.get('days', 30)

            # 1. Aggregate Data 
            # TODO: Wire to CommunicationAggregator once the Communications app is built
            snapshot_payload = {
                "generated_at": timezone.now().isoformat(),
                "period_days": days,
                "total_sent": 0,
                "total_delivered": 0,
                "total_failed": 0,
                "delivery_rate": 0.0,
                "breakdown_by_channel": []
            }

            # 2. Save Immutable Snapshot
            ReportSnapshot.objects.create(
                report=report,
                snapshot_data=snapshot_payload
            )

            # 3. Generate Export
            filename = f"communication_report_{report.id}_{timezone.now().strftime('%Y%m%d')}.xlsx"
            export_result = ExcelExporter.generate_excel_from_data(
                snapshot_payload,
                filename,
                sheet_name="Communication Delivery"
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
            logger.error(f"Failed to process communication report {report_id}: {str(e)}")
            Report.objects.filter(id=report_id).update(
                status=Report.Status.FAILED,
                error_message=str(e),
                completed_at=timezone.now()
            )