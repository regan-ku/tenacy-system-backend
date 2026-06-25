from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

router.register(r'tenancies', views.TenancyViewSet, basename='tenancy')
router.register(r'occupancy', views.OccupancyViewSet, basename='occupancy')
router.register(r'notes', views.TenancyNoteViewSet, basename='tenancy-note')
router.register(r'waivers', views.TenancyWaiverViewSet, basename='tenancy-waiver')

urlpatterns = [
    path('', include(router.urls)),
    
    # ✅ FIX: Changed 'list' to 'history' to match the ViewSet method name
    path(
        'tenants/<int:tenant_id>/history/', 
        views.TenantHistoryViewSet.as_view({'get': 'history'}), 
        name='tenant-history'
    ),
    path(
        'tenants/<int:tenant_id>/history/summary/', 
        views.TenantHistoryViewSet.as_view({'get': 'summary'}), 
        name='tenant-history-summary'
    ),
    
    path(
        'applications/<int:application_id>/tenant-profile/', 
        views.ApplicationTenantProfileView.as_view({'get': 'retrieve'}), 
        name='application-tenant-profile'
    ),
]