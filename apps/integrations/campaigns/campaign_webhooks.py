import logging
from ..models import WebhookEvent, MessageLog
from .campaign_tracker import CampaignTracker

logger = logging.getLogger(__name__)

class CampaignWebhookHandler:
    @staticmethod
    def process_delivery_callback(payload: dict):
        """
        Matches inbound delivery webhook to MessageLog → updates Campaign.total_delivered
        """
        msg_id = payload.get("message_id") or payload.get("external_ref")
        status = payload.get("status")
        
        if not msg_id:
            return {"status": "ignored", "reason": "no_message_id"}

        try:
            log = MessageLog.objects.filter(external_ref=msg_id).first()
            if log and log.message_type == "campaign":
                campaign_id = log.metadata.get("campaign_id") if hasattr(log, 'metadata') else None
                # In production: link via FK. For now, infer from metadata or raw payload
                if campaign_id:
                    CampaignTracker.increment_delivered(campaign_id)
                return {"status": "updated", "campaign_id": campaign_id}
            return {"status": "not_found", "message_id": msg_id}
        except Exception as e:
            logger.error(f"Campaign delivery callback failed: {str(e)}")
            return {"status": "failed", "error": str(e)}

    @staticmethod
    def queue_campaign_event(payload: dict):
        WebhookEvent.objects.create(
            source="campaign_delivery",
            event_type="campaign_delivery_update",
            payload=payload,
            processed=False
        )