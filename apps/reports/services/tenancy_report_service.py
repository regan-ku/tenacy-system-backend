import logging
from django.db import transaction
from django.utils import timezone

from ..models import Report, ReportSnapshot
from ..aggregators import TenancyAggregator, PropertyAggregator
from ..exporters.excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)

class TenancyReportService:
    """
    Handles the generation of Tenancy & Tenant History Reports.
    """

    @staticmethod
    @transaction.atomic
    def initiate_tenancy_report(user, title: str, parameters: dict) -> Report:
        """
        Creates a Report record and triggers background processing for tenancy data.
        """
        report = Report.objects.create(
            title=title,
            report_type=Report.ReportType.TENANCY,
            generated_by=user,
            parameters=parameters,
            status=Report.Status.PENDING
        )
        
        # In production: TenancyReportService._process_report_task.delay(report.id)
        TenancyReportService._process_report(report.id)
        return report

    @staticmethod
    def _process_report(report_id: int):
        """
        Core processing logic for the tenancy report.
        """
        try:
            report = Report.objects.select_related('generated_by').get(id=report_id)
            report.status = Report.Status.PROCESSING
            report.save(update_fields=['status'])

            user = report.generated_by

            # 1. Aggregate Data
            occupancy_summary = TenancyAggregator.get_occupancy_summary(user)
            upcoming_expiries = TenancyAggregator.get_upcoming_expiries(user, days_threshold=90)
            unit_distribution = PropertyAggregator.get_unit_type_distribution(user)

            snapshot_payload = {
                "generated_at": timezone.now().isoformat(),
                "occupancy_summary": occupancy_summary,
                "unit_distribution": unit_distribution,
                "upcoming_expiries": upcoming_expiries,
                "total_expiring_soon": len(upcoming_expiries)
            }

            # 2. Save Immutable Snapshot
            ReportSnapshot.objects.create(
                report=report,
                snapshot_data=snapshot_payload
            )

            # 3. Generate Export (Excel is ideal for tabular tenant lists)
            filename = f"tenancy_report_{report.id}_{timezone.now().strftime('%Y%m%d')}.xlsx"
            export_result = ExcelExporter.generate_excel_from_data(
                snapshot_payload,
                filename,
                sheet_name="Tenancy Data"
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
            logger.error(f"Failed to process tenancy report {report_id}: {str(e)}")
            Report.objects.filter(id=report_id).update(
                status=Report.Status.FAILED,
                error_message=str(e),
                completed_at=timezone.now()
            )