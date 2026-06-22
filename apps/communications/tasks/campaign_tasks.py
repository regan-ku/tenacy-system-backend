from celery import shared_task
import logging
from django.utils import timezone
from ..models import Campaign, CampaignStatus, Message, MessageStatus
from .messaging_tasks import dispatch_message_task
from ..utils.message_builder import MessageBuilder

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def dispatch_campaign_batch(self, campaign_id: str, user_ids_chunk: list, template_id: str) -> dict:
    """
    Iterates over a chunk of user IDs, creates message records, and triggers dispatch.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        if campaign.status != CampaignStatus.RUNNING:
            return {"status": "skipped", "reason": "Campaign not running"}

        # Render template once for context
        context = {"campaign_title": campaign.title}
        
        processed_count = 0
        for user_id in user_ids_chunk:
            try:
                # 1. Create Message Record
                message_content = MessageBuilder.render_template(template_id, context)["body"]
                
                message = Message.objects.create(
                    recipient_id=user_id,
                    channel=campaign.channel,
                    message_type="campaign",
                    content=message_content,
                    status=MessageStatus.QUEUED,
                    metadata={"campaign_id": campaign_id}
                )

                # 2. Trigger Dispatch
                dispatch_message_task.delay(
                    message_id=str(message.id),
                    channel=campaign.channel,
                    payload={"content": message_content}
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to queue message for user {user_id}: {str(e)}")

        # Update campaign metrics
        campaign.total_sent += processed_count
        campaign.save(update_fields=["total_sent"])
        
        return {"status": "completed", "processed": processed_count}
    except Exception as e:
        logger.error(f"Campaign batch task failed for {campaign_id}: {str(e)}")
        self.retry(exc=e)