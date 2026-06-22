from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# 1. Core Tenancy Management (Includes activate, add_note actions)
router.register(r'tenancies', views.TenancyViewSet, basename='tenancy')

# 2. Occupancy State
router.register(r'occupancy', views.OccupancyViewSet, basename='occupancy')

# 3. Notes & Waivers
router.register(r'notes', views.TenancyNoteViewSet, basename='tenancy-note')
router.register(r'waivers', views.TenancyWaiverViewSet, basename='tenancy-waiver')

urlpatterns = [
    # Include all standard router URLs
    path('', include(router.urls)),
    
    # ==============================================================================
    # EXPLICIT PATHS FOR DOCUMENTATION-SPECIFIC ENDPOINTS
    # ==============================================================================
    
    # Tenant History & Summary
    path(
        'tenants/<int:tenant_id>/history/', 
        views.TenantHistoryViewSet.as_view({'get': 'list'}), 
        name='tenant-history'
    ),
    path(
        'tenants/<int:tenant_id>/history/summary/', 
        views.TenantHistoryViewSet.as_view({'get': 'summary'}), 
        name='tenant-history-summary'
    ),
    
    # Cross-App Reference: Fetch tenant profile during application review
    path(
        'applications/<int:application_id>/tenant-profile/', 
        views.ApplicationTenantProfileView.as_view({'get': 'retrieve'}), 
        name='application-tenant-profile'
    ),
]