import logging
from django.http import HttpResponse, HttpRequest, JsonResponse
from ..whatsapp.webhook_handler import WhatsAppWebhookHandler
from ..whatsapp.chatbot_service import ChatbotService

logger = logging.getLogger(__name__)

class WhatsAppWebhook:
    @staticmethod
    def handle_webhook(request: HttpRequest) -> HttpResponse:
        """
        Main entry point for WhatsApp Cloud API webhooks.
        Distinguishes between verification (GET) and messages/status (POST).
        """
        if request.method == "GET":
            return WhatsAppWebhook.verify_token(request)
        elif request.method == "POST":
            return WhatsAppWebhook.process_payload(request)
        return HttpResponse(status=405)

    @staticmethod
    def verify_token(request: HttpRequest) -> HttpResponse:
        """Handles the initial subscription verification from Meta"""
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        from ..whatsapp.whatsapp_config import WhatsAppConfig
        verify_params = WhatsAppConfig.get_verify_params()
        expected_token = verify_params.get("hub.verify_token")

        if mode == "subscribe" and token == expected_token:
            logger.info("Webhook verified successfully.")
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)

    @staticmethod
    def process_payload(request: HttpRequest) -> HttpResponse:
        """
        Processes messages and status updates.
        """
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received WhatsApp Payload")

            # 1. Check for status updates
            statuses = WhatsAppWebhookHandler.process_status_update(data)
            if statuses.get("processed", 0) > 0:
                return JsonResponse({"status": "processed_status", "count": statuses["processed"]})

            # 2. Check for inbound messages
            entry = data.get("entry", [])
            if entry:
                changes = entry[0].get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    if messages:
                        for msg in messages:
                            phone = value.get("contacts", [{}])[0].get("wa_id")
                            text = msg.get("text", {}).get("body", "")
                            
                            # Route to chatbot if text exists
                            if text:
                                ChatbotService.route_inbound(text, phone)
                        
                        # Queue raw event
                        WhatsAppWebhookHandler.queue_inbound_message(data)

            return JsonResponse({"status": "received"})
        except Exception as e:
            logger.error(f"WhatsApp Webhook Error: {str(e)}")
            return JsonResponse({"status": "error"}, status=500)