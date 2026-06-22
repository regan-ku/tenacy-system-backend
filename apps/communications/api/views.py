from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.shortcuts import get_object_or_404

from .serializers import (
    MessageSerializer, NotificationSerializer, NotificationMarkReadSerializer,
    CampaignSerializer, CampaignCreateSerializer, MessageTemplateSerializer
)
from ..models import Message, Notification, Campaign, MessageTemplate
from ..permissions.communication_permissions import (
    IsMessageRecipientOrManager, CanViewOwnNotifications,
    CanManageCampaigns, CanViewTemplates
)
from ..services.campaign_service import CampaignService
from ..services.notification_service import NotificationService


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, CanViewOwnNotifications]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")

    @extend_schema(
        operation_id="communications_notifications_mark_read_update",
        responses={200: OpenApiResponse(description="Notification marked as read")}
    )
    @action(detail=True, methods=["patch"], url_path="mark-read")
    def mark_read(self, request, id=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"status": "read", "id": str(notification.id)})

    # ✅ FIXED: Explicit operation_id and url_path to resolve collision warning
    @extend_schema(
        operation_id="communications_notifications_mark_all_read_create",
        responses={200: OpenApiResponse(description="All notifications marked as read")}
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({"status": "all_marked_read"})


class MessageHistoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsMessageRecipientOrManager]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Message.objects.none()
        user = self.request.user
        if user.is_staff:
            return Message.objects.all().order_by("-created_at")
        return Message.objects.filter(recipient=user).order_by("-created_at")


class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageCampaigns]
    lookup_field = "id"

    def get_serializer_class(self):
        return CampaignCreateSerializer if self.request.method == "POST" else CampaignSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Campaign.objects.none()
        user = self.request.user
        if user.is_staff:
            return Campaign.objects.all().order_by("-created_at")
        return Campaign.objects.filter(creator=user).order_by("-created_at")

    @extend_schema(
        operation_id="communications_campaigns_send_create",
        request=CampaignCreateSerializer,
        responses={200: OpenApiResponse(description="Campaign execution triggered")}
    )
    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, id=None):
        campaign = self.get_object()
        if campaign.status not in ["draft", "scheduled"]:
            return Response({"error": "Campaign is already processed"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = CampaignService.execute_campaign(campaign.id)
            return Response(result)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MessageTemplateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated, CanViewTemplates]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return MessageTemplate.objects.none()
        return MessageTemplate.objects.filter(is_active=True).order_by("name")