from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Initialize the router for standard ViewSet routing
router = DefaultRouter()
router.register(r'agencies', views.AgencyViewSet, basename='agency')

urlpatterns = [
    # 1. Base Router URLs (e.g., /api/agencies/, /api/agencies/1/)
    path('', include(router.urls)),
    
    # 2. Nested Agency Resources
    
    # Directors
    path('agencies/<int:agency_pk>/directors/', views.AgencyDirectorViewSet.as_view({
        'get': 'list', 'post': 'create'
    }), name='agency-director-list'),
    
    path('agencies/<int:agency_pk>/directors/<int:pk>/', views.AgencyDirectorViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='agency-director-detail'),

    # Verification
    path('agencies/<int:agency_pk>/verification/', views.AgencyVerificationViewSet.as_view({
        'get': 'status', 'put': 'submit', 'patch': 'submit'
    }), name='agency-verification'),

    # Business Profile
    path('agencies/<int:agency_pk>/profile/', views.AgencyProfileViewSet.as_view({
        'get': 'retrieve_profile', 'put': 'update_profile', 'patch': 'update_profile'
    }), name='agency-profile'),

    # Staff Management
    path('agencies/<int:agency_pk>/staff/', views.AgencyStaffViewSet.as_view({
        'get': 'list', 'post': 'create'
    }), name='agency-staff-list'),

    path('agencies/<int:agency_pk>/staff/<int:pk>/', views.AgencyStaffViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='agency-staff-detail'),
    
    path('agencies/<int:agency_pk>/staff/<int:pk>/deactivate/', views.AgencyStaffViewSet.as_view({
        'post': 'deactivate'
    }), name='agency-staff-deactivate'),

    # Property Delegations
    path('agencies/<int:agency_pk>/delegations/', views.DelegationViewSet.as_view({
        'get': 'list', 'post': 'create'
    }), name='agency-delegation-list'),

    path('agencies/<int:agency_pk>/delegations/<int:pk>/', views.DelegationViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='agency-delegation-detail'),

    path('agencies/<int:agency_pk>/delegations/<int:pk>/revoke/', views.DelegationViewSet.as_view({
        'post': 'revoke'
    }), name='agency-delegation-revoke'),
]