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
]