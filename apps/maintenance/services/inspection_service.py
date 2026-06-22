from django.db import transaction
from ..models import MaintenanceInspection, MaintenanceCategory
from .request_service import RequestService
import logging

logger = logging.getLogger(__name__)

class InspectionService:
    @staticmethod
    @transaction.atomic
    def schedule_inspection(property, unit, inspector, inspection_date, findings=""):
        """Creates a new inspection record."""
        inspection = MaintenanceInspection.objects.create(
            property=property,
            unit=unit,
            inspector=inspector,
            inspection_date=inspection_date,
            findings=findings,
            status="scheduled"
        )
        logger.info(f"Inspection scheduled for {property.title} ({unit.unit_code}) on {inspection_date}")
        return inspection

    @staticmethod
    @transaction.atomic
    def complete_inspection(inspection_id, inspector, findings="", create_request=False, category_id=None):
        """
        Marks inspection complete. Optionally auto-creates a maintenance request if issues found.
        """
        inspection = MaintenanceInspection.objects.get(id=inspection_id, inspector=inspector)
        inspection.findings = findings
        inspection.status = "completed"
        inspection.save(update_fields=["findings", "status"])

        if create_request and category_id and inspection.unit:
            RequestService.create_request(
                created_by=inspector,
                unit=inspection.unit,
                title=f"Inspection Finding: {MaintenanceCategory.objects.get(id=category_id).name}",
                description=findings,
                category_id=category_id,
                priority="medium"
            )

        logger.info(f"Inspection {inspection_id} completed.")
        return inspection