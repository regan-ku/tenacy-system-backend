import logging
from django.db import transaction
from django.utils import timezone

from ..models import Report, ReportSnapshot
from ..aggregators import PaymentAggregator, PropertyAggregator
from ..utils.date_helpers import DateHelperUtils
from ..exporters.pdf_exporter import PDFExporter

logger = logging.getLogger(__name__)

class FinancialReportService:
    """
    Handles the generation of Financial & Revenue Reports.
    Manages the async lifecycle: PENDING -> PROCESSING -> COMPLETED/FAILED.
    """

    @staticmethod
    @transaction.atomic
    def initiate_financial_report(user, title: str, parameters: dict) -> Report:
        """
        Creates a Report record in PENDING status and triggers background processing.
        In production, this would dispatch a Celery task.
        """
        report = Report.objects.create(
            title=title,
            report_type=Report.ReportType.FINANCIAL,
            generated_by=user,
            parameters=parameters,
            status=Report.Status.PENDING
        )
        
        FinancialReportService._process_report(report.id)
        
        return report

    @staticmethod
    def _process_report(report_id: int):
        """
        Core processing logic for the financial report.
        """
        try:
            report = Report.objects.select_related('generated_by').get(id=report_id)
            report.status = Report.Status.PROCESSING
            report.save(update_fields=['status'])

            user = report.generated_by
            params = report.parameters

            # 1. Resolve Date Range
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            if not start_date or not end_date:
                start_date, end_date = DateHelperUtils.get_current_month_range()

            # 2. Aggregate Data (Strictly scoped to user)
            financial_summary = PaymentAggregator.get_financial_summary(user, start_date, end_date)
            portfolio_summary = PropertyAggregator.get_portfolio_summary(user)
            revenue_trend = PaymentAggregator.get_revenue_trend(user, months=6)

            snapshot_payload = {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "financial_summary": financial_summary,
                "portfolio_summary": portfolio_summary,
                "revenue_trend": revenue_trend,
                "currency": "KES"
            }

            # 3. Save Immutable Snapshot
            ReportSnapshot.objects.create(
                report=report,
                snapshot_data=snapshot_payload
            )

            # 4. Generate Export using DocumentTemplate system
            filename = f"financial_report_{report.id}_{timezone.now().strftime('%Y%m%d')}.pdf"
            export_result = PDFExporter.generate_pdf_from_document_template(
                document_type_code="financial_report",
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
            logger.error(f"Failed to process financial report {report_id}: {str(e)}")
            Report.objects.filter(id=report_id).update(
                status=Report.Status.FAILED,
                error_message=str(e),
                completed_at=timezone.now()
            )