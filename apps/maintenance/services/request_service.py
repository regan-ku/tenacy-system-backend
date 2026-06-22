from django.db import transaction
from django.utils import timezone
from ..models import MaintenanceRequest, MaintenanceHistory, MaintenanceCategory
from ..utils.priority_calculator import PriorityCalculator
from ..utils.sla_calculator import SLACalculator
import logging

logger = logging.getLogger(__name__)

class RequestService:
    @staticmethod
    @transaction.atomic
    def create_request(created_by, unit, title, description, category_id, priority=None):
        """
        Creates a new maintenance request.
        Auto-calculates priority from description and computes SLA deadline.
        """
        category = MaintenanceCategory.objects.get(id=category_id)
        
        # 1. Auto-triage priority if not explicitly provided
        final_priority = priority or PriorityCalculator.calculate_from_description(description)
        
        # 2. Calculate SLA deadline based on priority & category defaults
        sla_due_at = SLACalculator.calculate_due_at(timezone.now(), category.default_sla_hours, final_priority)

        # 3. Create request
        request = MaintenanceRequest.objects.create(
            created_by=created_by,
            unit=unit,
            property=unit.property,
            category=category,
            title=title,
            description=description,
            priority=final_priority,
            status="open",
            sla_due_at=sla_due_at
        )

        # 4. Log creation to immutable audit history
        MaintenanceHistory.objects.create(
            request=request,
            event_type="created",
            new_value={"title": title, "priority": final_priority, "status": "open"},
            performed_by=created_by
        )

        logger.info(f"Maintenance request {request.id} created for unit {unit.unit_code}")
        return request