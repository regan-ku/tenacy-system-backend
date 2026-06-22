from celery import shared_task
import logging
from ..models import Campaign, CampaignStatus
from ..campaigns.campaign_sender import CampaignSender
from ..campaigns.campaign_audience_builder import CampaignAudienceBuilder

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_campaign_batch(self, campaign_id: str, user_ids_chunk: list, context_template: dict = None):
    """
    Dispatches a specific batch of users for a campaign.
    Retries if the batch fails to prevent partial sends.
    """
    try:
        # Validate campaign status before sending
        campaign = Campaign.objects.get(id=campaign_id)
        if campaign.status not in [CampaignStatus.RUNNING, CampaignStatus.SCHEDULED]:
            return f"Skipped: Campaign {campaign_id} is no longer active"

        CampaignSender.dispatch_batch(campaign_id, user_ids_chunk, context_template)
        return f"Batch dispatched for campaign {campaign_id}"
    except Campaign.DoesNotExist:
        return f"Skipped: Campaign {campaign_id} not found"
    except Exception as e:
        logger.error(f"Campaign Batch Task Failed: {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=2)
def execute_campaign_full(self, campaign_id: str):
    """
    Orchestrates the full campaign run: Resolve Audience -> Split -> Queue Batches.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        user_ids = CampaignAudienceBuilder.resolve_audience(campaign.target_audience)
        
        # Split into chunks of 100 (matches CampaignSender.BATCH_SIZE)
        batch_size = 100
        for i in range(0, len(user_ids), batch_size):
            chunk = user_ids[i : i + batch_size]
            run_campaign_batch.delay(campaign_id, chunk, {})
            
        campaign.status = CampaignStatus.RUNNING
        campaign.save(update_fields=["status"])
        return f"Campaign {campaign_id} execution queued ({len(user_ids)} recipients)"
    except Exception as e:
        logger.error(f"Campaign Execution Task Failed: {str(e)}")
        self.retry(exc=e)