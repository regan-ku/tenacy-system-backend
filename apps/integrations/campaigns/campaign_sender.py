import logging
from typing import List, Dict, Any
from ..models import Campaign, MessageLog
from .campaign_templates import CampaignTemplateRenderer
from .campaign_tracker import CampaignTracker
from ..services.notification_router import NotificationRouter

logger = logging.getLogger(__name__)

class CampaignSender:
    BATCH_SIZE = 100  # Prevents provider rate-limit bans

    @classmethod
    def dispatch_batch(cls, campaign_id: str, user_ids: List[str], context_template: Dict[str, Any]):
        """
        Sends messages in chunks, logs each dispatch, and updates metrics.
        """
        campaign = Campaign.objects.get(id=campaign_id)
        template = campaign.message_template
        channel = campaign.channel

        for i in range(0, len(user_ids), cls.BATCH_SIZE):
            batch = user_ids[i:i + cls.BATCH_SIZE]
            sent_count = 0

            for user_id in batch:
                # Build user context (lazy-loaded in production via bulk query)
                user_context = {"user_id": str(user_id)}
                message = CampaignTemplateRenderer.render(template, {**user_context, **context_template})

                # Dispatch via notification router
                result = NotificationRouter.route_and_dispatch(
                    recipient_id=user_id,
                    message=message,
                    message_type="campaign",
                    metadata={"campaign_id": campaign_id}
                )

                if result.get("status") in ["queued", "success"]:
                    sent_count += 1
                    CampaignTracker.increment_sent(campaign_id)

            logger.info(f"Campaign {campaign_id}: Batch {i//cls.BATCH_SIZE + 1} sent {sent_count} messages")
            
        CampaignTracker.mark_completed(campaign_id)