from typing import List, Dict, Any
from django.db import transaction
from ..models import Campaign, CampaignStatus, CampaignAudience
import logging

logger = logging.getLogger(__name__)

class CampaignService:
    @staticmethod
    @transaction.atomic
    def execute_campaign(campaign_id: str):
        campaign = Campaign.objects.get(id=campaign_id)
        if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
            raise ValueError("Campaign is not in a dispatchable state")

        campaign.status = CampaignStatus.RUNNING
        campaign.save(update_fields=["status"])

        # Resolve target audience from attached segments
        audiences = CampaignAudience.objects.filter(campaign=campaign)
        user_ids = []
        for aud in audiences:
            # In production: use utils/audience_filters to resolve dynamically
            if isinstance(aud.filter_criteria, dict) and "user_ids" in aud.filter_criteria:
                user_ids.extend(aud.filter_criteria["user_ids"])

        unique_users = list(set(user_ids))
        campaign.total_sent = len(unique_users)
        campaign.save(update_fields=["total_sent"])

        # Dispatch in chunks to background workers
        from ..tasks.campaign_tasks import dispatch_campaign_batch
        for i in range(0, len(unique_users), 100):
            batch = unique_users[i:i+100]
            dispatch_campaign_batch.delay(campaign_id, batch, campaign.template_id)

        logger.info(f"Campaign {campaign_id} queued for {len(unique_users)} recipients")
        return {"status": "dispatching", "total_targets": len(unique_users)}