from django.core.exceptions import ValidationError
from ..models import Campaign, CampaignStatus
from .campaign_audience_builder import CampaignAudienceBuilder
from .campaign_sender import CampaignSender
from ..utils.audience_filters import validate_audience_size
import logging

logger = logging.getLogger(__name__)

class CampaignService:
    @staticmethod
    def execute_campaign(campaign_id: str):
        """
        Full execution pipeline: validate → resolve audience → dispatch → track
        """
        campaign = Campaign.objects.get(id=campaign_id)
        if campaign.status in [CampaignStatus.RUNNING, CampaignStatus.COMPLETED]:
            raise ValidationError("Campaign already processed.")

        # 1. Validate audience
        user_ids = CampaignAudienceBuilder.resolve_audience(campaign.target_audience)
        size_check = validate_audience_size(len(user_ids))
        if not size_check["is_valid"]:
            raise ValidationError(size_check["message"])

        # 2. Update status
        campaign.status = CampaignStatus.RUNNING
        campaign.save(update_fields=["status"])

        # 3. Trigger async dispatch
        CampaignSender.dispatch_batch.delay(campaign_id, user_ids, {})

        logger.info(f"Campaign {campaign_id} execution started for {len(user_ids)} recipients")
        return campaign_id