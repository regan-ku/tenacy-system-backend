from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, RequestViewSet, InspectionViewSet, unit_maintenance_history

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"requests", RequestViewSet, basename="request")
router.register(r"inspections", InspectionViewSet, basename="inspection")

urlpatterns = [
    path("", include(router.urls)),
    path("units/<uuid:unit_id>/history/", unit_maintenance_history, name="unit-history-public"),
]