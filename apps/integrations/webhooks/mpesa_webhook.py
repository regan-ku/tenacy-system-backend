import logging
import json
from django.http import JsonResponse, HttpRequest
from ..mpesa.callback_handler import MpesaCallbackHandler
from ..services.integration_logger import IntegrationLogger

# ✅ CRITICAL FIX: Import the gateway that bridges to the Payments app
from apps.payments.integrations.mpesa_service import MpesaPaymentGateway

logger = logging.getLogger(__name__)

class MpesaWebhook:
    @staticmethod
    def handle_stk_callback(request: HttpRequest) -> JsonResponse:
        """
        Receives STK push result callback, processes it, and records the payment.
        """
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            if not data:
                # Fallback to raw body if DRF hasn't processed it yet
                data = json.loads(request.body)
            
            logger.info(f"Received M-Pesa STK Callback: {data}")
            
            # ✅ CRITICAL FIX: Delegate to the Payment Gateway to actually record & allocate the payment
            result = MpesaPaymentGateway.process_stk_callback(data)
            
            if result.get("status") in ["recorded", "ignored"]:
                # "ignored" is a SUCCESS here: it means our idempotency check caught a duplicate Safaricom callback
                MpesaCallbackHandler.queue_webhook_event("mpesa_stk", data)
                # Safaricom expects a 200 OK to know we received it
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"}, status=200)
            
            # If it failed internally (e.g., Invoice not found), we STILL return 200 OK to Safaricom.
            # Returning a 500 causes Safaricom to retry endlessly, spamming your logs.
            # We rely on our IntegrationLogger to alert us to reconcile it manually.
            logger.error(f"M-Pesa Callback Processing Failed Internally: {result}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Processing failed, logged for manual review"}, status=200)
            
        except Exception as e:
            logger.error(f"STK Callback Critical Error: {str(e)}")
            IntegrationLogger.log_failure("mpesa_stk_callback", str(e), increment_retry=False)
            # Always return 200 to Safaricom to prevent infinite retry loops
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Internal server error"}, status=200)

    @staticmethod
    def handle_c2b_validation(request: HttpRequest) -> JsonResponse:
        from ..mpesa.c2b_service import C2BService
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received C2B Validation: {data}")
            result = C2BService.handle_validation_callback(data)
            return JsonResponse(result, status=200)
        except Exception as e:
            logger.error(f"C2B Validation Error: {str(e)}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Internal Error"}, status=200)

    @staticmethod
    def handle_c2b_confirmation(request: HttpRequest) -> JsonResponse:
        from ..mpesa.c2b_service import C2BService
        try:
            data = request.data if hasattr(request, 'data') else request.POST
            logger.info(f"Received C2B Confirmation: {data}")
            result = C2BService.handle_confirmation_callback(data)
            return JsonResponse(result, status=200)
        except Exception as e:
            logger.error(f"C2B Confirmation Error: {str(e)}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Internal Error"}, status=200)