from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from django.contrib.auth import get_user_model

from . import serializers
from ..models import Profile, NextOfKin, Verification
from ..services import AuthService, UserService
from ..permissions.access_control import IsRole, IsVerifiedUser

User = get_user_model()


@extend_schema_view(
    me=extend_schema(summary="Get Current User Profile", responses={200: serializers.ProfileSerializer}),
    update_profile=extend_schema(
        summary="Update User Profile", 
        request=serializers.ProfileSerializer,
        responses={200: serializers.ProfileSerializer}
    ),
    user_state=extend_schema(
        summary="Post-Login User State Resolution",
        description="Evaluates user state and returns the exact `next_route` the frontend must navigate to.",
        responses={200: serializers.UserStateResponseSerializer}
    ),
    upgrade_role=extend_schema(
        summary="Request Role Upgrade",
        description="Allows a Tenant to request an upgrade to Landlord or Agency.",
        request=serializers.RoleUpgradeSerializer,
        responses={200: serializers.UserStateResponseSerializer}
    ),
    # ✅ ADDED: Schema for the new onboarding completion endpoint
    complete_onboarding=extend_schema(
        summary="Complete Onboarding",
        description="Handles the final onboarding submission including profile, next of kin, and verification documents.",
        responses={200: OpenApiResponse(description="Onboarding completed successfully")}
    )
)
class ProfileViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Profile.objects.select_related('user').filter(user=self.request.user)

    @extend_schema(responses={200: serializers.ProfileSerializer})
    @action(detail=False, methods=['GET'], url_path='me')
    def me(self, request):
        profile = self.get_queryset().first()
        if not profile:
            profile = Profile.objects.create(user=request.user)
        return Response(self.get_serializer(profile).data)

    @extend_schema(request=serializers.ProfileSerializer, responses={200: serializers.ProfileSerializer})
    @action(detail=False, methods=['PATCH', 'PUT'], url_path='update')
    def update_profile(self, request):
        profile = self.get_queryset().first()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(serializer.save()).data)

    @extend_schema(responses={200: serializers.UserStateResponseSerializer})
    @action(detail=False, methods=['GET'], url_path='state')
    def user_state(self, request):
        return Response(UserService.get_user_state(request.user), status=status.HTTP_200_OK)

    @extend_schema(request=serializers.RoleUpgradeSerializer, responses={200: serializers.UserStateResponseSerializer})
    @action(
        detail=False, 
        methods=['POST'], 
        url_path='upgrade',
        permission_classes=[permissions.IsAuthenticated, IsRole(User.Role.TENANT)] 
    )
    def upgrade_role(self, request):
        serializer = serializers.RoleUpgradeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)

    # ✅ ADDED: The missing endpoint that was causing the 404 error!
    @action(detail=False, methods=['POST'], url_path='complete')
    def complete_onboarding(self, request):
        """
        Handles the final onboarding submission.
        Delegates business logic to UserService to keep the view clean.
        """
        try:
            profile = UserService.complete_onboarding(
                user=request.user, 
                data=request.data, 
                files=request.FILES
            )
            return Response({
                "message": "Onboarding completed successfully", 
                "profile_complete": profile.profile_complete
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    register=extend_schema(
        summary="User Registration",
        description="Registers a new user with email, phone, password, and role.",
        request=serializers.UserRegistrationSerializer, 
        responses={201: OpenApiResponse(description="User registered successfully"), 400: OpenApiResponse(description="Invalid data")}
    ),
    login=extend_schema(
        summary="User Login",
        description="Authenticates credentials and returns JWT tokens.",
        request=serializers.LoginSerializer,
        responses={200: OpenApiResponse(description="Successful login"), 400: OpenApiResponse(description="Invalid credentials")}
    )
)
class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    @action(detail=False, methods=['POST'], url_path='register')
    def register(self, request):
        serializer = serializers.UserRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"message": "User registered successfully", "user_id": user.id},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], url_path='login')
    def login(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({"error": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            tokens = AuthService.login_user(email, password)
            return Response(tokens, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class NextOfKinViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.NextOfKinSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return NextOfKin.objects.none()
            
        if not self.request.user.is_authenticated:
            return NextOfKin.objects.none()
            
        return NextOfKin.objects.filter(user=self.request.user).order_by('-is_primary', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class VerificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.VerificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Verification.objects.none()
            
        if not self.request.user.is_authenticated:
            return Verification.objects.none()
            
        return Verification.objects.filter(user=self.request.user)

    @extend_schema(summary="Get Verification Status", responses={200: serializers.VerificationSerializer})
    @action(detail=False, methods=['GET'], url_path='status')
    def status(self, request):
        verification = self.get_queryset().first()
        if not verification:
            return Response({"status": "not_submitted"}, status=status.HTTP_200_OK)
        return Response(self.get_serializer(verification).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Submit Verification Documents",
        description="Submits ID, KRA, and Tax Cert. Requires multipart/form-data.",
        request=serializers.VerificationSerializer,
        responses={200: serializers.VerificationSerializer}
    )
    @action(detail=False, methods=['PUT', 'PATCH'], url_path='submit')
    def submit(self, request):
        verification = self.get_queryset().first()
        if not verification:
            verification = Verification.objects.create(user=request.user)
            
        serializer = self.get_serializer(verification, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(serializer.save()).data, status=status.HTTP_200_OK)