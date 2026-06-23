from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# Base Property routes
router.register(r'properties', views.PropertyViewSet, basename='property')

urlpatterns = [
    path('', include(router.urls)),
    
    # Nested Unit Group routes: /api/properties/<id>/unit-groups/
    path('properties/<int:property_pk>/unit-groups/', views.UnitGroupViewSet.as_view({
        'get': 'list', 'post': 'create'
    }), name='property-unit-group-list'),
    
    path('properties/<int:property_pk>/unit-groups/<int:pk>/', views.UnitGroupViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='property-unit-group-detail'),

    # ✅ FIX: Nested Unit routes: Added 'post': 'create' to allow adding units
    path('properties/<int:property_pk>/units/', views.UnitViewSet.as_view({
        'get': 'list', 'post': 'create' 
    }), name='property-unit-list'),
    
    path('properties/<int:property_pk>/units/<int:pk>/', views.UnitViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='property-unit-detail'),

    path('properties/<int:property_pk>/units/<int:pk>/update-status/', views.UnitViewSet.as_view({
        'patch': 'update_status'
    }), name='property-unit-update-status'),

    # Nested Media routes: /api/properties/<id>/media/
    path('properties/<int:property_pk>/media/', views.PropertyMediaViewSet.as_view({
        'get': 'list', 'post': 'create'
    }), name='property-media-list'),

    path('properties/<int:property_pk>/media/<int:pk>/', views.PropertyMediaViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='property-media-detail'),
]