from typing import Dict, Any, List
from django.contrib.auth import get_user_model
from ..utils.audience_filters import build_campaign_audience

User = get_user_model()

class CampaignAudienceBuilder:
    @staticmethod
    def resolve_audience(target_filters: Dict[str, Any]) -> List[str]:
        """
        Builds queryset from JSON filters and returns list of user IDs.
        Prevents N+1 queries and keeps audience resolution isolated.
        """
        if not target_filters:
            return []
            
        q_object = build_campaign_audience(target_filters)
        return list(User.objects.filter(q_object).values_list("id", flat=True))

    @staticmethod
    def validate_audience_size(user_ids: List[str], max_limit: int = 50000) -> Dict[str, Any]:
        """Prevents accidental platform-wide broadcasts"""
        count = len(user_ids)
        return {
            "is_valid": count <= max_limit,
            "count": count,
            "message": f"Audience size {count} exceeds safe broadcast limit ({max_limit})" if count > max_limit else "Valid audience"
        }