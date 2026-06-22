from rest_framework import viewsets, status, mixins
from rest_framework.decorators import APIView, action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.shortcuts import get_object_or_404

# ✅ FIXED: Updated to match renamed serializers in integrations.api.serializers
from .serializers import (
    PaymentTransactionSerializer, MessageLogSerializer, IntegrationLogSerializer,
    IntegrationCampaignSerializer, IntegrationCampaignCreateSerializer,
    StkPushRequestSerializer, SmsDispatchRequestSerializer, WhatsAppDispatchRequestSerializer
)
from ..models import PaymentTransaction, MessageLog, IntegrationLog, Campaign
from ..permissions.integration_permissions import (
    IsAdminOrSystemIntegrator, CanTriggerPayment, IsCampaignManager, IsWebhookService
)
from ..services.integration_logger import IntegrationLogger
from ..mpesa.stk_push_service import StkPushService
from ..webhooks.mpesa_webhook import MpesaWebhook
from ..africastalking.sms_service import SmsService
from ..whatsapp.whatsapp_service import WhatsAppService
from ..webhooks.africastalking_webhook import AfricasTalkingWebhook
from ..webhooks.whatsapp_webhook import WhatsAppWebhook
from ..campaigns.campaign_service import CampaignService
from ..campaigns.campaign_webhooks import CampaignWebhookHandler


class IntegrationLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = IntegrationLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSystemIntegrator]
    lookup_field = "id"
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return IntegrationLog.objects.none()
        return IntegrationLog.objects.all().order_by("-created_at")

class MessageLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSystemIntegrator]
    lookup_field = "id"
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return MessageLog.objects.none()
        return MessageLog.objects.all().order_by("-created_at")

class PaymentTransactionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSystemIntegrator]
    lookup_field = "id"
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return PaymentTransaction.objects.none()
        return PaymentTransaction.objects.all().order_by("-created_at")


class CampaignViewSet(viewsets.ModelViewSet):
    # ✅ FIXED: Updated serializer references
    serializer_class = IntegrationCampaignSerializer
    permission_classes = [IsAuthenticated, IsCampaignManager]
    lookup_field = "id"
    
    def get_serializer_class(self):
        return IntegrationCampaignCreateSerializer if self.request.method == "POST" else IntegrationCampaignSerializer
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Campaign.objects.none()
        return Campaign.objects.all().order_by("-created_at")

    @extend_schema(request=IntegrationCampaignCreateSerializer, responses={200: OpenApiResponse(description="Campaign execution triggered")})
    @action(detail=True, methods=["post"])
    def execute(self, request, id=None):
        campaign = self.get_object()
        try:
            result = CampaignService.execute_campaign(campaign.id)
            return Response({"status": "executing", "campaign_id": result})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(request=StkPushRequestSerializer, responses={200: OpenApiResponse(description="STK Push initiated")})
@api_view(["POST"])
@permission_classes([IsAuthenticated, CanTriggerPayment])
def trigger_stk_push(request):
    serializer = StkPushRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = StkPushService.initiate(
        phone=serializer.validated_data["phone"], amount=serializer.validated_data["amount"],
        account_ref=serializer.validated_data["account_ref"],
        transaction_desc=serializer.validated_data.get("transaction_desc", "Payment")
    )
    return Response(result, status=status.HTTP_200_OK if result["success"] else status.HTTP_400_BAD_REQUEST)


@extend_schema(request=SmsDispatchRequestSerializer, responses={200: OpenApiResponse(description="SMS dispatched")})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCampaignManager])
def dispatch_sms(request):
    serializer = SmsDispatchRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = SmsService.send_single(
        phone=serializer.validated_data["phone"], message=serializer.validated_data["message"],
        sender_id=serializer.validated_data.get("sender_id")
    )
    return Response(result, status=status.HTTP_200_OK if result["success"] else status.HTTP_400_BAD_REQUEST)


@extend_schema(request=WhatsAppDispatchRequestSerializer, responses={200: OpenApiResponse(description="WhatsApp message sent")})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCampaignManager])
def dispatch_whatsapp(request):
    serializer = WhatsAppDispatchRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone = serializer.validated_data["phone"]
    
    if serializer.validated_data.get("template_name"):
        result = WhatsAppService.send_template(
            phone=phone, template_name=serializer.validated_data["template_name"],
            language_code=serializer.validated_data.get("language_code", "en")
        )
    else:
        result = WhatsAppService.send_text(phone=phone, message=serializer.validated_data["text"])
        
    return Response(result, status=status.HTTP_200_OK if result["success"] else status.HTTP_400_BAD_REQUEST)


# ================= WEBHOOK ENDPOINTS =================
@extend_schema(request=None, responses={200: OpenApiResponse(description="M-Pesa webhook processed")})
class MpesaWebhookView(APIView):
    permission_classes = [IsWebhookService]
    def post(self, request, *args, **kwargs):
        hook_type = kwargs.get("hook_type")
        if hook_type == "stk":
            return MpesaWebhook.handle_stk_callback(request)
        elif hook_type == "c2b_validate":
            return MpesaWebhook.handle_c2b_validation(request)
        elif hook_type == "c2b_confirm":
            return MpesaWebhook.handle_c2b_confirmation(request)
        return Response({"error": "Invalid webhook type"}, status=400)

@extend_schema(request=None, responses={200: OpenApiResponse(description="AfricasTalking webhook processed")})
class AfricasTalkingWebhookView(APIView):
    permission_classes = [IsWebhookService]
    def post(self, request, *args, **kwargs):
        hook_type = kwargs.get("hook_type")
        if hook_type == "delivery":
            return AfricasTalkingWebhook.handle_delivery_report(request)
        elif hook_type == "sms":
            return AfricasTalkingWebhook.handle_inbound_sms(request)
        return Response({"error": "Invalid webhook type"}, status=400)

@extend_schema(request=None, responses={200: OpenApiResponse(description="WhatsApp webhook processed")})
class WhatsAppWebhookView(APIView):
    permission_classes = [IsWebhookService]
    def get(self, request): return WhatsAppWebhook.handle_webhook(request)
    def post(self, request): return WhatsAppWebhook.handle_webhook(request)

@extend_schema(request=None, responses={200: OpenApiResponse(description="Campaign delivery callback processed")})
class CampaignDeliveryWebhookView(APIView):
    permission_classes = [IsWebhookService]
    def post(self, request):
        result = CampaignWebhookHandler.process_delivery_callback(request.data)
        CampaignWebhookHandler.queue_campaign_event(request.data)
        return Response(result)