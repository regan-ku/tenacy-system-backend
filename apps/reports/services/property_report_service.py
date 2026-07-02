import logging
from django.db import transaction
from django.utils import timezone

from ..models import Report, ReportSnapshot
from ..aggregators import PropertyAggregator, TenancyAggregator
from ..exporters.pdf_exporter import PDFExporter

logger = logging.getLogger(__name__)

class PropertyReportService:
    """
    Handles the generation of Property Portfolio & Asset Reports.
    """

    @staticmethod
    @transaction.atomic
    def initiate_property_report(user, title: str, parameters: dict) -> Report:
        report = Report.objects.create(
            title=title,
            report_type=Report.ReportType.OCCUPANCY, # Reusing OCCUPANCY or add PROPERTY to choices if needed
            generated_by=user,
            parameters=parameters,
            status=Report.Status.PENDING
        )
        
        PropertyReportService._process_report(report.id)
        return report

    @staticmethod
    def _process_report(report_id: int):
        try:
            report = Report.objects.select_related('generated_by').get(id=report_id)
            report.status = Report.Status.PROCESSING
            report.save(update_fields=['status'])

            user = report.generated_by

            # 1. Aggregate Data
            portfolio_summary = PropertyAggregator.get_portfolio_summary(user)
            unit_distribution = PropertyAggregator.get_unit_type_distribution(user)
            occupancy_summary = TenancyAggregator.get_occupancy_summary(user)

            snapshot_payload = {
                "generated_at": timezone.now().isoformat(),
                "portfolio_summary": portfolio_summary,
                "unit_distribution": unit_distribution,
                "occupancy_summary": occupancy_summary
            }

            # 2. Save Immutable Snapshot
            ReportSnapshot.objects.create(
                report=report,
                snapshot_data=snapshot_payload
            )

            # 3. Generate Export using DocumentTemplate system
            filename = f"property_portfolio_report_{report.id}_{timezone.now().strftime('%Y%m%d')}.pdf"
            export_result = PDFExporter.generate_pdf_from_document_template(
                document_type_code="property_portfolio_report", # Must match DocumentType.code in DB
                variables={"data": snapshot_payload, "user": user.email},
                filename=filename
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
            logger.error(f"Failed to process property report {report_id}: {str(e)}")
            Report.objects.filter(id=report_id).update(
                status=Report.Status.FAILED,
                error_message=str(e),
                completed_at=timezone.now()
            )