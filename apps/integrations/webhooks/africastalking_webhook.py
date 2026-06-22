import logging
from django.http import JsonResponse, HttpRequest
from ..africastalking.delivery_report_handler import DeliveryReportHandler
from ..models import WebhookEvent

logger = logging.getLogger(__name__)

class AfricasTalkingWebhook:
    @staticmethod
    def handle_delivery_report(request: HttpRequest) -> JsonResponse:
        """
        Processes inbound SMS delivery status updates.
        """
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received AT Delivery Report: {data}")
            
            result = DeliveryReportHandler.process_report(data)
            DeliveryReportHandler.queue_delivery_event(data)
            
            return JsonResponse({"status": "success", "result": result})
        except Exception as e:
            logger.error(f"AT Delivery Report Error: {str(e)}")
            return JsonResponse({"status": "error"}, status=500)

    @staticmethod
    def handle_inbound_sms(request: HttpRequest) -> JsonResponse:
        """
        Processes inbound SMS from users.
        """
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received AT Inbound SMS: {data}")
            
            # Queue for async processing by application logic
            WebhookEvent.objects.create(
                source="africastalking",
                event_type="inbound_sms",
                payload=data,
                processed=False
            )
            
            return JsonResponse({"status": "queued"})
        except Exception as e:
            logger.error(f"AT Inbound SMS Error: {str(e)}")
            return JsonResponse({"status": "error"}, status=500)