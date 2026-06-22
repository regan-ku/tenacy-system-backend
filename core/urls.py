from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # 1. Django Admin
    path('admin/', admin.site.urls),
    
    # ==========================================
    # 2. API DOCUMENTATION (drf-spectacular)
    # ==========================================
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # ==========================================
    # 3. V1 API ENDPOINTS (ALL 12 APPS)
    # ==========================================
    
    # A. Identity & Onboarding
    path('api/v1/accounts/', include('apps.accounts.api.urls')),
    
    # B. Core Property & Tenancy Operations
    path('api/v1/properties/', include('apps.properties.api.urls')),
    path('api/v1/tenancies/', include('apps.tenancy.api.urls')),
    path('api/v1/applications/', include('apps.applications.api.urls')),
    
    # C. Financial & Field Operations
    path('api/v1/payments/', include('apps.payments.api.urls')),
    path('api/v1/maintenance/', include('apps.maintenance.api.urls')),
    
    # D. Communications & Documents
    path('api/v1/communications/', include('apps.communications.api.urls')),
    path('api/v1/documents/', include('apps.documents.api.urls')),
    
    # E. External Gateways & Enterprise Management
    path('api/v1/integrations/', include('apps.integrations.api.urls')),
    path('api/v1/agencies/', include('apps.agencies.api.urls')),
    
    # F. Public Marketplace & Intelligence
    # ✅ THIS LINE IS PERFECT. It correctly connects the marketplace app.
    path('api/v1/marketplace/', include('apps.marketplace.api.urls')),
    path('api/v1/reports/', include('apps.reports.api.urls')),
]

# Serve media and static files in development (for property images, IDs, PDFs)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)