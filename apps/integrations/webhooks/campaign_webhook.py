import logging
from django.http import JsonResponse, HttpRequest
from ..models import WebhookEvent

logger = logging.getLogger(__name__)

class CampaignWebhook:
    @staticmethod
    def handle_delivery_event(request: HttpRequest) -> JsonResponse:
        """
        Receives delivery callbacks for bulk campaigns.
        Updates campaign stats (sent/delivered counts) asynchronously.
        """
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received Campaign Delivery Event")
            
            WebhookEvent.objects.create(
                source="campaign_service",
                event_type="campaign_delivery",
                payload=data,
                processed=False
            )
            
            return JsonResponse({"status": "queued"})
        except Exception as e:
            logger.error(f"Campaign Webhook Error: {str(e)}")
            return JsonResponse({"status": "error"}, status=500)