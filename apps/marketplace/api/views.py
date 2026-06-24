# from rest_framework import viewsets, status, permissions
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter

# from . import serializers
# from ..models import Listing, SavedListing
# from apps.properties.models import Property 

# from ..services import (
#     ListingService, 
#     PublishingService, 
#     SavedListingService,
#     SearchService,
#     GeoMarketplaceService
# )
# from ..permissions.marketplace_permissions import (
#     IsMarketplaceReadOnly, 
#     CanManagePropertyPublication, 
#     CanSaveListings
# )


# @extend_schema_view(
#     list=extend_schema(
#         summary="List Marketplace Listings",
#         description="Returns a highly optimized list of active, visible listings for the landing page grid.",
#         responses={200: serializers.ListingSerializer(many=True)}
#     ),
#     retrieve=extend_schema(
#         summary="Get Listing Details",
#         description="Returns comprehensive details for a single listing, including property amenities and unit availability.",
#         responses={200: serializers.ListingDetailSerializer}
#     )
# )
# class MarketplaceListingViewSet(viewsets.ReadOnlyModelViewSet):
#     serializer_class = serializers.ListingSerializer
#     permission_classes = [IsMarketplaceReadOnly]

#     def get_queryset(self):
#         # ✅ Prevent drf-spectacular from crashing during schema generation
#         if getattr(self, 'swagger_fake_view', False):
#             return Listing.objects.none()
#         return ListingService.get_public_listings()

#     def get_serializer_class(self):
#         if self.action == 'retrieve':
#             return serializers.ListingDetailSerializer
#         return serializers.ListingSerializer

#     def retrieve(self, request, *args, **kwargs):
#         instance = self.get_object()
#         return super().retrieve(request, *args, **kwargs)


# @extend_schema_view(
#     publish=extend_schema(
#         summary="Publish Property to Marketplace",
#         description="Makes a property publicly visible. Validates media, location, and unit availability.",
#         request=serializers.PropertyPublicationActionSerializer,
#         responses={200: OpenApiResponse(description="Property published successfully")}
#     ),
#     hide=extend_schema(
#         summary="Hide Property from Marketplace",
#         description="Temporarily hides property without affecting internal operations.",
#         request=serializers.PropertyPublicationActionSerializer,
#         responses={200: OpenApiResponse(description="Property hidden successfully")}
#     ),
#     unpublish=extend_schema(
#         summary="Unpublish Property",
#         description="Removes property from marketplace entirely.",
#         request=serializers.PropertyPublicationActionSerializer,
#         responses={200: OpenApiResponse(description="Property unpublished successfully")}
#     ),
#     restore=extend_schema(
#         summary="Restore Property to Marketplace",
#         description="Re-publishes a previously hidden or unpublished property.",
#         request=serializers.PropertyPublicationActionSerializer,
#         responses={200: OpenApiResponse(description="Property restored successfully")}
#     )
# )
# class PropertyPublicationViewSet(viewsets.GenericViewSet):
#     permission_classes = [permissions.IsAuthenticated, CanManagePropertyPublication]
#     serializer_class = serializers.PropertyPublicationActionSerializer

#     # ✅ Prevent Spectacular crash
#     queryset = Property.objects.none()

#     def get_property(self, pk):
#         try:
#             return Property.objects.get(pk=pk)
#         except Property.DoesNotExist:
#             from rest_framework.exceptions import NotFound
#             raise NotFound("Property not found.")

#     @action(detail=True, methods=['POST'], url_path='publish')
#     def publish(self, request, pk=None):
#         property_obj = self.get_property(pk)
#         PublishingService.publish_property(property_obj, request.user)
#         return Response(
#             {"detail": "Property published to marketplace successfully."}, 
#             status=status.HTTP_200_OK
#         )

#     @action(detail=True, methods=['POST'], url_path='hide')
#     def hide(self, request, pk=None):
#         property_obj = self.get_property(pk)
#         PublishingService.hide_property(property_obj, request.user)
#         return Response(
#             {"detail": "Property hidden from marketplace successfully."}, 
#             status=status.HTTP_200_OK
#         )

#     @action(detail=True, methods=['POST'], url_path='unpublish')
#     def unpublish(self, request, pk=None):
#         property_obj = self.get_property(pk)
#         PublishingService.unpublish_property(property_obj, request.user)
#         return Response(
#             {"detail": "Property unpublished successfully."}, 
#             status=status.HTTP_200_OK
#         )

#     # ✅🚨 CRITICAL FIX: The restore action was missing but referenced in urls.py
#     @action(detail=True, methods=['POST'], url_path='restore')
#     def restore(self, request, pk=None):
#         """
#         Re-publishes a previously hidden or unpublished property.
#         Equivalent to publish but semantically indicates restoring visibility.
#         """
#         property_obj = self.get_property(pk)
#         PublishingService.publish_property(property_obj, request.user)
#         return Response(
#             {"detail": "Property restored to marketplace successfully."}, 
#             status=status.HTTP_200_OK
#         )


# class MarketplaceSearchViewSet(viewsets.GenericViewSet):
#     permission_classes = [IsMarketplaceReadOnly]
    
#     # ✅ Provide a dummy queryset so Spectacular can derive the model type
#     queryset = Listing.objects.none()

#     @extend_schema(
#         summary="Advanced Marketplace Search",
#         description="Search listings by text query and apply multiple filters (price, location, amenities).",
#         parameters=[
#             OpenApiParameter(name='q', description='Search query (location, title)', required=False, type=str),
#             OpenApiParameter(name='city', description='Filter by city', required=False, type=str),
#             OpenApiParameter(name='estate', description='Filter by estate/neighborhood', required=False, type=str),
#             OpenApiParameter(name='min_price', description='Minimum rent', required=False, type=float),
#             OpenApiParameter(name='max_price', description='Maximum rent', required=False, type=float),
#             OpenApiParameter(name='unit_type', description='Filter by unit type', required=False, type=str),
#             OpenApiParameter(name='property_type', description='Filter by property type', required=False, type=str),
#         ],
#         responses={200: serializers.ListingSerializer(many=True)}
#     )
#     @action(detail=False, methods=['GET'], url_path='search')
#     def search(self, request):
#         query = request.query_params.get('q', '')
#         filters = {
#             'city': request.query_params.get('city'),
#             'estate': request.query_params.get('estate'),
#             'min_price': request.query_params.get('min_price'),
#             'max_price': request.query_params.get('max_price'),
#             'unit_type': request.query_params.get('unit_type'),
#             'property_type': request.query_params.get('property_type'),
#         }
#         filters = {k: v for k, v in filters.items() if v is not None}
        
#         user = request.user if request.user.is_authenticated else None
#         session_id = request.session.session_key if request.session else None
        
#         try:
#             results, count = SearchService.search_marketplace(
#                 query=query, filters=filters, user=user, session_id=session_id
#             )
#             serializer = serializers.ListingSerializer(results, many=True)
#             return Response({"count": count, "results": serializer.data}, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     @extend_schema(
#         summary="Geo-Based Nearby Search",
#         description="Finds available units within a specific radius (in km) of provided GPS coordinates.",
#         parameters=[
#             OpenApiParameter(name='lat', description='Latitude', required=True, type=float),
#             OpenApiParameter(name='lng', description='Longitude', required=True, type=float),
#             OpenApiParameter(name='radius', description='Radius in kilometers (default 5)', required=False, type=float),
#         ],
#         responses={200: serializers.ListingDetailSerializer(many=True)}
#     )
#     @action(detail=False, methods=['GET'], url_path='nearby')
#     def nearby(self, request):
#         try:
#             lat = float(request.query_params.get('lat'))
#             lng = float(request.query_params.get('lng'))
#             radius = float(request.query_params.get('radius', 5.0))
#         except (TypeError, ValueError):
#             return Response(
#                 {"error": "Invalid latitude, longitude, or radius."}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             nearby_listings = GeoMarketplaceService.find_nearby_available_units(lat, lng, radius)
#             serializer = serializers.ListingDetailSerializer(nearby_listings, many=True)
#             return Response(
#                 {"count": len(nearby_listings), "results": serializer.data}, 
#                 status=status.HTTP_200_OK
#             )
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     # ✅ ADDED: Featured listings endpoint (expected by frontend endpoints.ts)
#     @extend_schema(
#         summary="Featured Listings",
#         description="Returns promoted/featured listings for the marketplace hero section.",
#         responses={200: serializers.ListingSerializer(many=True)}
#     )
#     @action(detail=False, methods=['GET'], url_path='featured')
#     def featured(self, request):
#         try:
#             featured_listings = ListingService.get_featured_listings()
#             serializer = serializers.ListingSerializer(featured_listings, many=True)
#             return Response({"results": serializer.data}, status=status.HTTP_200_OK)
#         except Exception:
#             # Fallback: return empty list if service method doesn't exist yet
#             return Response({"results": []}, status=status.HTTP_200_OK)


# class SavedListingViewSet(viewsets.ModelViewSet):
#     serializer_class = serializers.SavedListingSerializer
#     permission_classes = [permissions.IsAuthenticated, CanSaveListings]

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return SavedListing.objects.none()
#         return SavedListingService.get_user_saved_listings(self.request.user)

#     def perform_create(self, serializer):
#         serializer.save()

#     def destroy(self, request, *args, **kwargs):
#         instance = self.get_object()
#         SavedListingService.unsave_listing(request.user, instance.listing.id)
#         return Response(
#             {"detail": "Listing removed from saved list."}, 
#             status=status.HTTP_204_NO_CONTENT
#         ) 


from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter

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
from ..permissions.marketplace_permissions import (
    IsMarketplaceReadOnly, 
    CanManagePropertyPublication, 
    CanSaveListings
)


@extend_schema_view(
    list=extend_schema(
        summary="List Marketplace Listings",
        description="Returns a highly optimized list of active, visible listings for the landing page grid.",
        responses={200: serializers.ListingSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Get Listing Details",
        description="Returns comprehensive details for a single listing, including property amenities and unit availability.",
        responses={200: serializers.ListingDetailSerializer}
    )
)
class MarketplaceListingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.ListingSerializer
    permission_classes = [IsMarketplaceReadOnly]

    def get_queryset(self):
        # ✅ Prevent drf-spectacular from crashing during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Listing.objects.none()
            
        # ✅ FIX: The service now handles deduplication safely.
        # We DO NOT add .order_by() or .distinct() here, because doing so 
        # can conflict with DRF's pagination COUNT() query and trigger 
        # the "SELECT DISTINCT ON expressions must match" error.
        return ListingService.get_public_listings()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.ListingDetailSerializer
        return serializers.ListingSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return super().retrieve(request, *args, **kwargs)


@extend_schema_view(
    publish=extend_schema(
        summary="Publish Property to Marketplace",
        description="Makes a property publicly visible. Validates media, location, and unit availability.",
        request=serializers.PropertyPublicationActionSerializer,
        responses={200: OpenApiResponse(description="Property published successfully")}
    ),
    hide=extend_schema(
        summary="Hide Property from Marketplace",
        description="Temporarily hides property without affecting internal operations.",
        request=serializers.PropertyPublicationActionSerializer,
        responses={200: OpenApiResponse(description="Property hidden successfully")}
    ),
    unpublish=extend_schema(
        summary="Unpublish Property",
        description="Removes property from marketplace entirely.",
        request=serializers.PropertyPublicationActionSerializer,
        responses={200: OpenApiResponse(description="Property unpublished successfully")}
    ),
    restore=extend_schema(
        summary="Restore Property to Marketplace",
        description="Re-publishes a previously hidden or unpublished property.",
        request=serializers.PropertyPublicationActionSerializer,
        responses={200: OpenApiResponse(description="Property restored successfully")}
    )
)
class PropertyPublicationViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, CanManagePropertyPublication]
    serializer_class = serializers.PropertyPublicationActionSerializer

    # ✅ Prevent Spectacular crash
    queryset = Property.objects.none()

    def get_property(self, pk):
        try:
            return Property.objects.get(pk=pk)
        except Property.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Property not found.")

    @action(detail=True, methods=['POST'], url_path='publish')
    def publish(self, request, pk=None):
        property_obj = self.get_property(pk)
        PublishingService.publish_property(property_obj, request.user)
        return Response(
            {"detail": "Property published to marketplace successfully."}, 
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['POST'], url_path='hide')
    def hide(self, request, pk=None):
        property_obj = self.get_property(pk)
        PublishingService.hide_property(property_obj, request.user)
        return Response(
            {"detail": "Property hidden from marketplace successfully."}, 
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['POST'], url_path='unpublish')
    def unpublish(self, request, pk=None):
        property_obj = self.get_property(pk)
        PublishingService.unpublish_property(property_obj, request.user)
        return Response(
            {"detail": "Property unpublished successfully."}, 
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['POST'], url_path='restore')
    def restore(self, request, pk=None):
        property_obj = self.get_property(pk)
        PublishingService.publish_property(property_obj, request.user)
        return Response(
            {"detail": "Property restored to marketplace successfully."}, 
            status=status.HTTP_200_OK
        )


class MarketplaceSearchViewSet(viewsets.GenericViewSet):
    permission_classes = [IsMarketplaceReadOnly]
    
    # ✅ Provide a dummy queryset so Spectacular can derive the model type
    queryset = Listing.objects.none()

    @extend_schema(
        summary="Advanced Marketplace Search",
        description="Search listings by text query and apply multiple filters (price, location, amenities).",
        parameters=[
            OpenApiParameter(name='q', description='Search query (location, title)', required=False, type=str),
            OpenApiParameter(name='city', description='Filter by city', required=False, type=str),
            OpenApiParameter(name='estate', description='Filter by estate/neighborhood', required=False, type=str),
            OpenApiParameter(name='min_price', description='Minimum rent', required=False, type=float),
            OpenApiParameter(name='max_price', description='Maximum rent', required=False, type=float),
            OpenApiParameter(name='unit_type', description='Filter by unit type', required=False, type=str),
            OpenApiParameter(name='property_type', description='Filter by property type', required=False, type=str),
        ],
        responses={200: serializers.ListingSerializer(many=True)}
    )
    @action(detail=False, methods=['GET'], url_path='search')
    def search(self, request):
        query = request.query_params.get('q', '')
        filters = {
            'city': request.query_params.get('city'),
            'estate': request.query_params.get('estate'),
            'min_price': request.query_params.get('min_price'),
            'max_price': request.query_params.get('max_price'),
            'unit_type': request.query_params.get('unit_type'),
            'property_type': request.query_params.get('property_type'),
        }
        filters = {k: v for k, v in filters.items() if v is not None}
        
        user = request.user if request.user.is_authenticated else None
        session_id = request.session.session_key if request.session else None
        
        try:
            results, count = SearchService.search_marketplace(
                query=query, filters=filters, user=user, session_id=session_id
            )
            # ✅ NOTE: We do NOT distinct here. The frontend's Map deduplication 
            # will handle it, and doing so here would make the 'count' variable incorrect.
            serializer = serializers.ListingSerializer(results, many=True)
            return Response({"count": count, "results": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Geo-Based Nearby Search",
        description="Finds available units within a specific radius (in km) of provided GPS coordinates.",
        parameters=[
            OpenApiParameter(name='lat', description='Latitude', required=True, type=float),
            OpenApiParameter(name='lng', description='Longitude', required=True, type=float),
            OpenApiParameter(name='radius', description='Radius in kilometers (default 5)', required=False, type=float),
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
                {"error": "Invalid latitude, longitude, or radius."}, 
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
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Featured Listings",
        description="Returns promoted/featured listings for the marketplace hero section.",
        responses={200: serializers.ListingSerializer(many=True)}
    )
    @action(detail=False, methods=['GET'], url_path='featured')
    def featured(self, request):
        try:
            featured_listings = ListingService.get_featured_listings()
            serializer = serializers.ListingSerializer(featured_listings, many=True)
            return Response({"results": serializer.data}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"results": []}, status=status.HTTP_200_OK)


class SavedListingViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.SavedListingSerializer
    permission_classes = [permissions.IsAuthenticated, CanSaveListings]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SavedListing.objects.none()
        return SavedListingService.get_user_saved_listings(self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        SavedListingService.unsave_listing(request.user, instance.listing.id)
        return Response(
            {"detail": "Listing removed from saved list."}, 
            status=status.HTTP_204_NO_CONTENT
        )