from typing import List, Dict, Any
from ..models import MaintenanceRequest, MaintenanceHistory, MaintenanceMedia

class UnitHistoryService:
    @staticmethod
    def get_public_unit_history(unit_id: str, include_media: bool = True) -> List[Dict[str, Any]]:
        """
        Fetches maintenance history for a specific unit.
        Returns sanitized, read-only view suitable for tenant/applicant dashboards.
        """
        # 1. Fetch all resolved/closed requests for this unit
        requests = MaintenanceRequest.objects.filter(
            unit_id=unit_id,
            status__in=["resolved", "closed"]
        ).select_related("category")

        history = []
        for req in requests:
            # 2. Get latest audit log entry for resolution context
            latest_log = MaintenanceHistory.objects.filter(
                request=req,
                event_type__in=["resolved", "closed"]
            ).order_by("-created_at").first()

            entry = {
                "request_id": str(req.id),
                "title": req.title,
                "category": req.category.name,
                "priority": req.get_priority_display(),
                "status": req.get_status_display(),
                "created_at": req.created_at.strftime("%Y-%m-%d"),
                "resolved_at": req.resolved_at.strftime("%Y-%m-%d") if req.resolved_at else None,
                "description": latest_log.new_value.get("summary", "") if latest_log else req.description,
            }

            # 3. Optional: attach before/after media for transparency
            if include_media:
                media = MaintenanceMedia.objects.filter(request=req, is_before_after=True).values("media_type", "file_url", "caption")
                entry["evidence"] = list(media)

            history.append(entry)

        return sorted(history, key=lambda x: x["created_at"], reverse=True)

    @staticmethod
    def get_unit_health_summary(unit_id: str) -> Dict[str, Any]:
        """
        Quick KPI summary shown during application review.
        """
        total = MaintenanceRequest.objects.filter(unit_id=unit_id, status__in=["resolved", "closed"]).count()
        emergency = MaintenanceRequest.objects.filter(unit_id=unit_id, priority="emergency", status="resolved").count()

        return {
            "total_issues_resolved": total,
            "emergency_cases": emergency,
            "unit_condition_rating": "Good" if emergency == 0 and total < 3 else "Moderate" if total < 6 else "High Maintenance"
        }