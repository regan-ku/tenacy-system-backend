from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationViewSet, MessageHistoryViewSet, CampaignViewSet, MessageTemplateViewSet
)

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"messages", MessageHistoryViewSet, basename="message-history")
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"templates", MessageTemplateViewSet, basename="template")

urlpatterns = [
    path("", include(router.urls)),
    # Explicit action endpoints for clarity & frontend routing
    path("notifications/mark-all-read/", NotificationViewSet.as_view({"post": "mark_all_read"}), name="mark-all-notifications-read"),
    path("campaigns/<uuid:id>/send/", CampaignViewSet.as_view({"post": "send"}), name="send-campaign"),
]