from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# 1. Public Marketplace Listings (Read-Only)
router.register(r'listings', views.MarketplaceListingViewSet, basename='marketplace-listing')

# 2. Saved Listings (Requires Auth)
router.register(r'saved', views.SavedListingViewSet, basename='saved-listing')

# ✅ FIX: Register the Search ViewSet with the router.
# Because the @action decorators have url_path='search', 'nearby', 'featured',
# and we register it with an empty prefix '', the router will generate:
# /search/, /nearby/, /featured/
router.register(r'', views.MarketplaceSearchViewSet, basename='marketplace-search')

urlpatterns = [
    # Include base router URLs (This now includes listings, saved, AND search/nearby/featured)
    path('', include(router.urls)),
    
    # 3. Property Publication Control (Owner/Manager Only)
    # These remain manual because they are specific property actions, not a general ViewSet
    path('properties/<int:pk>/publish/', views.PropertyPublicationViewSet.as_view({'post': 'publish'}), name='property-publish'),
    path('properties/<int:pk>/hide/', views.PropertyPublicationViewSet.as_view({'post': 'hide'}), name='property-hide'),
    path('properties/<int:pk>/unpublish/', views.PropertyPublicationViewSet.as_view({'post': 'unpublish'}), name='property-unpublish'),
    path('properties/<int:pk>/restore/', views.PropertyPublicationViewSet.as_view({'post': 'restore'}), name='property-restore'),
]