from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter
from django.core.exceptions import ValidationError

from . import serializers
from ..models import Listing, SavedListing
from apps.properties.models import Property

from ..services import (
    ListingService,
    PublishingService,
    SavedListingService,
    SearchService,
    GeoMarketplaceService
)
from ..services.featured_listing_service import FeaturedListingService
from ..permissions.marketplace_permissions import (
    IsMarketplaceReadOnly,
    CanManagePropertyPublication,
    CanSaveListings
)


# ===========================================================================
# 1. PUBLIC MARKETPLACE LISTINGS (Read-Only)
# ===========================================================================
@extend_schema_view(
    list=extend_schema(
        summary="List Marketplace Listings",
        description=(
            "Returns a highly optimized list of active, visible listings "
            "for the landing page grid. Only published properties with "
            "available units are returned."
        ),
        responses={200: serializers.ListingSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Get Listing Details",
        description=(
            "Returns comprehensive details for a single listing, including "
            "property amenities, unit groups, media, and availability."
        ),
        responses={200: serializers.ListingDetailSerializer}
    )
)
class MarketplaceListingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public-facing viewset for marketplace listings.
    No authentication required for browsing.
    """
    serializer_class = serializers.ListingSerializer
    permission_classes = [IsMarketplaceReadOnly]
    lookup_field = 'pk'

    def get_queryset(self):
        # Prevent drf-spectacular from crashing during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Listing.objects.none()

        # The service handles deduplication and visibility filtering
        return ListingService.get_public_listings()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.ListingDetailSerializer
        return serializers.ListingSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Fetch a single listing with full details.
        Returns 404 if listing is not found or not publicly visible.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================================================================
# 2. PROPERTY PUBLICATION CONTROL (Owner/Manager Only)
# ===========================================================================
@extend_schema_view(
    publish=extend_schema(
        summary="Publish Property to Marketplace",
        description=(
            "Makes a property publicly visible. Validates that the property "
            "has media, location data, and at least one available unit."
        ),
        request=serializers.PropertyPublicationActionSerializer,
        responses={
            200: OpenApiResponse(description="Property published successfully"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Property not found"),
        }
    ),
    hide=extend_schema(
        summary="Hide Property from Marketplace",
        description=(
            "Temporarily hides property from public view without affecting "
            "internal operations (tenancy, payments continue normally)."
        ),
        request=serializers.PropertyPublicationActionSerializer,
        responses={
            200: OpenApiResponse(description="Property hidden successfully"),
            404: OpenApiResponse(description="Property not found"),
        }
    ),
    unpublish=extend_schema(
        summary="Unpublish Property",
        description="Removes property from marketplace entirely.",
        request=serializers.PropertyPublicationActionSerializer,
        responses={
            200: OpenApiResponse(description="Property unpublished successfully"),
            404: OpenApiResponse(description="Property not found"),
        }
    ),
    restore=extend_schema(
        summary="Restore Property to Marketplace",
        description=(
            "Re-publishes a previously hidden or unpublished property. "
            "Subject to the same validation rules as initial publish."
        ),
        request=serializers.PropertyPublicationActionSerializer,
        responses={
            200: OpenApiResponse(description="Property restored successfully"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Property not found"),
        }
    )
)
class PropertyPublicationViewSet(viewsets.GenericViewSet):
    """
    Controls marketplace visibility for properties.
    Only property owners or delegated managers can invoke these actions.
    """
    permission_classes = [permissions.IsAuthenticated, CanManagePropertyPublication]
    serializer_class = serializers.PropertyPublicationActionSerializer

    # Dummy queryset for Spectacular schema generation
    queryset = Property.objects.none()

    def get_property(self, pk):
        """
        Retrieves the property and verifies the requesting user
        has management rights over it.
        """
        try:
            property_obj = Property.objects.select_related(
                'created_by', 'current_manager', 'location'
            ).get(pk=pk)
        except Property.DoesNotExist:
            raise NotFound("Property not found.")

        # Verify the user has authority over this property
        user = self.request.user
        is_owner = property_obj.created_by == user
        is_manager = property_obj.current_manager == user

        if not is_owner and not is_manager:
            raise PermissionDenied(
                "You do not have permission to manage this property's publication."
            )

        return property_obj

    @action(detail=True, methods=['POST'], url_path='publish')
    def publish(self, request, pk=None):
        property_obj = self.get_property(pk)
        try:
            PublishingService.publish_property(property_obj, request.user)
            return Response(
                {"detail": "Property published to marketplace successfully."},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['POST'], url_path='hide')
    def hide(self, request, pk=None):
        property_obj = self.get_property(pk)
        try:
            PublishingService.hide_property(property_obj, request.user)
            return Response(
                {"detail": "Property hidden from marketplace successfully."},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['POST'], url_path='unpublish')
    def unpublish(self, request, pk=None):
        property_obj = self.get_property(pk)
        try:
            PublishingService.unpublish_property(property_obj, request.user)
            return Response(
                {"detail": "Property unpublished successfully."},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['POST'], url_path='restore')
    def restore(self, request, pk=None):
        property_obj = self.get_property(pk)
        try:
            PublishingService.publish_property(property_obj, request.user)
            return Response(
                {"detail": "Property restored to marketplace successfully."},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ===========================================================================
# 3. MARKETPLACE SEARCH & DISCOVERY
# ===========================================================================
class MarketplaceSearchViewSet(viewsets.GenericViewSet):
    """
    Handles all marketplace search, geo-based discovery, and featured listings.
    Registered with the router using an empty prefix so actions resolve to:
      /search/, /nearby/, /featured/
    """
    permission_classes = [IsMarketplaceReadOnly]

    # Dummy queryset for Spectacular schema derivation
    queryset = Listing.objects.none()

    @extend_schema(
        summary="Advanced Marketplace Search",
        description=(
            "Search listings by text query and apply multiple filters "
            "(price, location, unit type, property type). Returns paginated results."
        ),
        parameters=[
            OpenApiParameter(
                name='q',
                description='Free-text search query (matches title, city, estate)',
                required=False, type=str
            ),
            OpenApiParameter(
                name='city',
                description='Filter by city (exact match)',
                required=False, type=str
            ),
            OpenApiParameter(
                name='estate',
                description='Filter by estate/neighborhood (exact match)',
                required=False, type=str
            ),
            OpenApiParameter(
                name='min_price',
                description='Minimum rent amount',
                required=False, type=float
            ),
            OpenApiParameter(
                name='max_price',
                description='Maximum rent amount',
                required=False, type=float
            ),
            OpenApiParameter(
                name='unit_type',
                description='Filter by unit type (single, bedsitter, one_bedroom, two_bedroom, commercial)',
                required=False, type=str
            ),
            OpenApiParameter(
                name='property_type',
                description='Filter by property type (residential, commercial, mixed_use, industrial, hospitality)',
                required=False, type=str
            ),
        ],
        responses={200: serializers.ListingSerializer(many=True)}
    )
    @action(detail=False, methods=['GET'], url_path='search')
    def search(self, request):
        query = request.query_params.get('q', '').strip()

        filters = {
            'city': request.query_params.get('city'),
            'estate': request.query_params.get('estate'),
            'min_price': request.query_params.get('min_price'),
            'max_price': request.query_params.get('max_price'),
            'unit_type': request.query_params.get('unit_type'),
            'property_type': request.query_params.get('property_type'),
        }
        # Remove empty/None filters
        filters = {k: v for k, v in filters.items() if v is not None and v != ''}

        user = request.user if request.user.is_authenticated else None
        session_id = request.session.session_key if hasattr(request, 'session') else None

        try:
            results, count = SearchService.search_marketplace(
                query=query,
                filters=filters,
                user=user,
                session_id=session_id
            )
            serializer = serializers.ListingSerializer(results, many=True)
            return Response(
                {"count": count, "results": serializer.data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "An error occurred while searching. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Geo-Based Nearby Search",
        description=(
            "Finds available units within a specific radius (in km) of "
            "provided GPS coordinates. Uses geohash-based spatial queries."
        ),
        parameters=[
            OpenApiParameter(
                name='lat',
                description='Latitude coordinate',
                required=True, type=float
            ),
            OpenApiParameter(
                name='lng',
                description='Longitude coordinate',
                required=True, type=float
            ),
            OpenApiParameter(
                name='radius',
                description='Search radius in kilometers (default: 5.0)',
                required=False, type=float
            ),
        ],
        responses={200: serializers.ListingDetailSerializer(many=True)}
    )
    @action(detail=False, methods=['GET'], url_path='nearby')
    def nearby(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
            radius = float(request.query_params.get('radius', 5.0))
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid latitude, longitude, or radius. All must be numeric."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate coordinate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response(
                {"error": "Latitude must be between -90 and 90, longitude between -180 and 180."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if radius <= 0 or radius > 100:
            return Response(
                {"error": "Radius must be between 0.1 and 100 kilometers."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            nearby_listings = GeoMarketplaceService.find_nearby_available_units(lat, lng, radius)
            serializer = serializers.ListingDetailSerializer(nearby_listings, many=True)
            return Response(
                {"count": len(nearby_listings), "results": serializer.data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "An error occurred while fetching nearby listings."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Featured Listings",
        description=(
            "Returns promoted/featured listings for the marketplace hero section. "
            "These are manually curated or premium listings."
        ),
        responses={200: serializers.ListingSerializer(many=True)}
    )
    @action(detail=False, methods=['GET'], url_path='featured')
    def featured(self, request):
        """
        Returns active featured listings.
        Extracts actual Listing objects from FeaturedListing wrappers.
        """
        try:
            featured_qs = FeaturedListingService.get_active_featured_listings()
            listings = [f.listing for f in featured_qs if f.listing]
            serializer = serializers.ListingSerializer(listings, many=True)
            return Response(
                {"results": serializer.data},
                status=status.HTTP_200_OK
            )
        except Exception:
            # Graceful fallback: return empty list if service fails
            return Response(
                {"results": []},
                status=status.HTTP_200_OK
            )


# ===========================================================================
# 4. SAVED LISTINGS (Authenticated Users Only)
# ===========================================================================
class SavedListingViewSet(viewsets.ModelViewSet):
    """
    Allows authenticated users to save/bookmark marketplace listings.
    Supports: list, create, retrieve, delete.
    """
    serializer_class = serializers.SavedListingSerializer
    permission_classes = [permissions.IsAuthenticated, CanSaveListings]
    http_method_names = ['get', 'post', 'delete']  # No PATCH/PUT needed

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SavedListing.objects.none()
        return SavedListingService.get_user_saved_listings(self.request.user)

    def perform_create(self, serializer):
        """
        Save a listing for the current user.
        The serializer's create method handles deduplication.
        """
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Remove a listing from the user's saved list.
        """
        instance = self.get_object()

        # Verify ownership
        if instance.user != request.user:
            raise PermissionDenied("You can only remove your own saved listings.")

        SavedListingService.unsave_listing(request.user, instance.listing.id)
        return Response(
            {"detail": "Listing removed from saved list."},
            status=status.HTTP_200_OK
        )