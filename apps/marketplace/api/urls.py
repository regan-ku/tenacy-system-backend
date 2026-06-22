from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# 1. Public Marketplace Listings (Read-Only)
router.register(r'listings', views.MarketplaceListingViewSet, basename='marketplace-listing')

# 2. Saved Listings (Requires Auth)
router.register(r'saved', views.SavedListingViewSet, basename='saved-listing')

urlpatterns = [
    # Include base router URLs
    path('', include(router.urls)),
    
    # 3. Search & Discovery Endpoints
    path('search/', views.MarketplaceSearchViewSet.as_view({'get': 'search'}), name='marketplace-search'),
    path('nearby/', views.MarketplaceSearchViewSet.as_view({'get': 'nearby'}), name='marketplace-nearby'),
    path('featured/', views.MarketplaceSearchViewSet.as_view({'get': 'featured'}), name='marketplace-featured'),
    
    # 4. Property Publication Control (Owner/Manager Only)
    path('properties/<int:pk>/publish/', views.PropertyPublicationViewSet.as_view({'post': 'publish'}), name='property-publish'),
    path('properties/<int:pk>/hide/', views.PropertyPublicationViewSet.as_view({'post': 'hide'}), name='property-hide'),
    path('properties/<int:pk>/unpublish/', views.PropertyPublicationViewSet.as_view({'post': 'unpublish'}), name='property-unpublish'),
    path('properties/<int:pk>/restore/', views.PropertyPublicationViewSet.as_view({'post': 'restore'}), name='property-restore'),
]