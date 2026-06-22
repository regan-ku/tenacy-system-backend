from celery import shared_task
from django.utils import timezone
from ..models import Campaign, CampaignStatus
from .campaign_service import CampaignService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def execute_scheduled_campaigns(self):
    """
    Scans for campaigns scheduled in the past that are still in DRAFT/SCHEDULED state.
    Triggers execution via CampaignService.
    """
    now = timezone.now()
    scheduled = Campaign.objects.filter(
        status__in=[CampaignStatus.DRAFT, CampaignStatus.SCHEDULED],
        scheduled_at__lte=now
    )

    executed = 0
    for campaign in scheduled:
        try:
            CampaignService.execute_campaign(campaign.id)
            executed += 1
        except Exception as e:
            logger.error(f"Failed to execute campaign {campaign.id}: {str(e)}")
            
    return f"Executed {executed} scheduled campaigns"