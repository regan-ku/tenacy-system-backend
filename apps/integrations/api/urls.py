from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    IntegrationLogViewSet, MessageLogViewSet, PaymentTransactionViewSet,
    CampaignViewSet, trigger_stk_push, dispatch_sms, dispatch_whatsapp,
    MpesaWebhookView, AfricasTalkingWebhookView, WhatsAppWebhookView, CampaignDeliveryWebhookView
)

router = DefaultRouter()
router.register(r"logs/integrations", IntegrationLogViewSet, basename="integration-logs")
router.register(r"logs/messages", MessageLogViewSet, basename="message-logs")
router.register(r"transactions", PaymentTransactionViewSet, basename="payment-transactions")
router.register(r"campaigns", CampaignViewSet, basename="campaigns")

urlpatterns = [
    path("", include(router.urls)),
    
    # Dispatch Actions
    path("mpesa/stk-push/", trigger_stk_push, name="stk-push"),
    path("sms/send/", dispatch_sms, name="sms-dispatch"),
    path("whatsapp/send/", dispatch_whatsapp, name="whatsapp-dispatch"),
    
    # Inbound Webhooks (Public/Provider Access)
    path("webhooks/mpesa/<str:hook_type>/", MpesaWebhookView.as_view(), name="mpesa-webhook"),
    path("webhooks/africastalking/<str:hook_type>/", AfricasTalkingWebhookView.as_view(), name="at-webhook"),
    path("webhooks/whatsapp/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
    path("webhooks/campaign/delivery/", CampaignDeliveryWebhookView.as_view(), name="campaign-webhook"),
]