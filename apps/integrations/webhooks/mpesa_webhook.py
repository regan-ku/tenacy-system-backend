import logging
from django.http import JsonResponse, HttpRequest
from ..mpesa.callback_handler import MpesaCallbackHandler
from ..services.integration_logger import IntegrationLogger

logger = logging.getLogger(__name__)

class MpesaWebhook:
    @staticmethod
    def handle_stk_callback(request: HttpRequest) -> JsonResponse:
        """
        Receives STK push result callback.
        Delegates to MpesaCallbackHandler for parsing and queueing.
        """
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            if not data:
                # Try parsing raw body if DRF hasn't processed it
                import json
                data = json.loads(request.body)
            
            logger.info(f"Received M-Pesa STK Callback: {data}")
            result = MpesaCallbackHandler.process_stk_callback(data)
            
            if result.get("status") == "completed":
                MpesaCallbackHandler.queue_webhook_event("mpesa_stk", data)
                
            return JsonResponse({"status": "received", "code": "00"})
        except Exception as e:
            logger.error(f"STK Callback Error: {str(e)}")
            IntegrationLogger.log_failure("unknown", str(e), increment_retry=False)
            return JsonResponse({"status": "error"}, status=500)

    @staticmethod
    def handle_c2b_validation(request: HttpRequest) -> JsonResponse:
        """
        Validates transaction before M-Pesa processes it.
        """
        from ..mpesa.c2b_service import C2BService
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received C2B Validation: {data}")
            result = C2BService.handle_validation_callback(data)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f"C2B Validation Error: {str(e)}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Internal Error"}, status=500)

    @staticmethod
    def handle_c2b_confirmation(request: HttpRequest) -> JsonResponse:
        """
        Confirms transaction after M-Pesa processes it.
        """
        from ..mpesa.c2b_service import C2BService
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received C2B Confirmation: {data}")
            result = C2BService.handle_confirmation_callback(data)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f"C2B Confirmation Error: {str(e)}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Internal Error"}, status=500)