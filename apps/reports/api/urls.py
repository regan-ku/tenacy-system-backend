from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# 1. Dashboard Endpoint (Role-based, read-only)
router.register(r'dashboards', views.DashboardViewSet, basename='report-dashboard')

# 2. Report Generation & Status Tracking
router.register(r'reports', views.ReportViewSet, basename='report-generation')

# 3. Report Schedules (NEW: Actively uses CanManageReportSchedules permission)
router.register(r'schedules', views.ReportScheduleViewSet, basename='report-schedule')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboards/me/', views.DashboardViewSet.as_view({'get': 'retrieve'}), name='dashboard-me'),
]# apps/reports/api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# 1. Dashboard Endpoint (Role-based, read-only)
router.register(r'dashboards', views.DashboardViewSet, basename='report-dashboard')

# 2. Report Generation & Status Tracking
router.register(r'reports', views.ReportViewSet, basename='report-generation')

# 3. Report Schedules
router.register(r'schedules', views.ReportScheduleViewSet, basename='report-schedule')

urlpatterns = [
    path('', include(router.urls)),
    
    # ✅ EXPLICIT ROUTING: Bypasses DRF @action router caching issues
    path('reports/portfolio-metrics/', views.ReportViewSet.as_view({'get': 'portfolio_metrics'}), name='portfolio-metrics'),
    path('reports/maintenance-analytics/', views.ReportViewSet.as_view({'get': 'maintenance_analytics'}), name='maintenance-analytics'),
    path('reports/landlord-statements/', views.ReportViewSet.as_view({'get': 'landlord_statements'}), name='landlord-statements'),
    path('reports/statements/<str:statement_id>/export/pdf/', views.ReportViewSet.as_view({'get': 'export_statement_pdf'}), name='export-statement-pdf'),
    
    # Dashboard me endpoint
    path('dashboards/me/', views.DashboardViewSet.as_view({'get': 'retrieve'}), name='dashboard-me'),
]