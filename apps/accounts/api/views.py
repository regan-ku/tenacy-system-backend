from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from django.utils import timezone

from django.contrib.auth import get_user_model

from . import serializers
from ..models import Profile, NextOfKin, Verification
from ..services import AuthService, UserService
from ..permissions.access_control import IsRole, IsVerifiedUser

# ✅ IMPORT: Required to auto-terminate property assignments & fetch them
from apps.properties.models.staff_assignment import PropertyStaffAssignment

User = get_user_model()

# ✅ Custom throttle for critical initialization endpoints to prevent 429 errors
class BurstRateThrottle(UserRateThrottle):
    rate = '1000/minute'


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
    complete_onboarding=extend_schema(
        summary="Complete Onboarding",
        description="Handles the final onboarding submission including profile, next of kin, and verification documents.",
        responses={200: OpenApiResponse(description="Onboarding completed successfully")}
    )
)
class ProfileViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle]

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

    @action(detail=False, methods=['POST'], url_path='complete')
    def complete_onboarding(self, request):
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


# ==========================================
# 6. MANAGER-INITIATED TENANT CREATION
# ==========================================
@extend_schema_view(
    create_tenant=extend_schema(
        summary="Manager Create Tenant",
        description="Allows a manager/landlord/agency to create a new tenant account, profile, and next of kin.",
        request=serializers.ManagerCreateTenantSerializer,
        responses={201: OpenApiResponse(description="Tenant created successfully")}
    )
)
class ManagerTenantViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.ManagerCreateTenantSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['POST'], url_path='create')
    def create_tenant(self, request):
        allowed_roles = [User.Role.LANDLORD, User.Role.AGENCY, User.Role.AGENT, User.Role.ADMIN]
        if request.user.role not in allowed_roles:
            return Response(
                {"error": "You do not have permission to create tenant accounts."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            "message": "Tenant account created successfully.",
            "tenant_id": result['user'].id,
            "email": result['user'].email,
            "temp_password": result['temp_password'] 
        }, status=status.HTTP_201_CREATED)


# ==========================================
# 7. APPLICANT RESOLUTION & STAFF MANAGEMENT (UPDATED)
# ==========================================
@extend_schema_view(
    lookup_applicant=extend_schema(
        summary="Lookup Applicant",
        description="Smart lookup to check if an applicant exists and what data is missing.",
        request=serializers.LookupApplicantSerializer,
        responses={200: OpenApiResponse(description="Lookup result")}
    ),
    create_staff=extend_schema(
        summary="Create Staff Member",
        description="Allows a manager to create a staff member (Agent/Caretaker/Property Manager) with a ghost profile.",
        request=serializers.StaffCreateSerializer,
        responses={201: OpenApiResponse(description="Staff created successfully")}
    ),
    list_staff=extend_schema(
        summary="List Staff Members",
        description="Fetches all agents, caretakers, and property managers managed by the logged-in user.",
        responses={200: OpenApiResponse(description="List of staff members")}
    ),
    deactivate_staff=extend_schema(
        summary="Deactivate Staff Member",
        description="Revokes a staff member's access to the system, logs the reason, and auto-terminates property assignments.",
        responses={200: OpenApiResponse(description="Staff deactivated successfully")}
    ),
    # ✅ NEW: Schema for Get Staff Assignments
    get_staff_assignments=extend_schema(
        summary="Get Staff Property Assignments",
        description="Fetches all active property assignments for a specific staff member.",
        responses={200: OpenApiResponse(description="List of property assignments")}
    )
)
class ApplicantManagementViewSet(viewsets.GenericViewSet):
    """
    ViewSet for resolving applicants (Smart Lookup), creating staff members, listing staff, and deactivating staff.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['POST'], url_path='lookup')
    def lookup_applicant(self, request):
        serializer = serializers.LookupApplicantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = UserService.lookup_applicant(
            email=serializer.validated_data.get('email'),
            phone=serializer.validated_data.get('phone_number')
        )
        
        user_data = None
        if result['user']:
            profile = getattr(result['user'], 'profile', None)
            user_data = {
                "id": result['user'].id,
                "email": result['user'].email,
                "phone_number": result['user'].phone_number,
                "full_name": profile.full_name if profile else None
            }
            
        return Response({
            "status": result['status'],
            "role": result['role'],
            "missing_fields": result['missing_fields'],
            "user": user_data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['POST'], url_path='create-staff')
    def create_staff(self, request):
        allowed_roles = [User.Role.LANDLORD, User.Role.AGENCY, User.Role.AGENT, User.Role.ADMIN]
        if request.user.role not in allowed_roles:
            return Response(
                {"error": "You do not have permission to create staff accounts."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = serializers.StaffCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            "message": "Staff account created successfully.",
            "staff_id": result['user'].id,
            "email": result['user'].email,
            "role": result['user'].role,
            "temp_password": result['temp_password']
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['GET'], url_path='list-staff')
    def list_staff(self, request):
        if request.user.role not in [User.Role.LANDLORD, User.Role.AGENCY, User.Role.ADMIN]:
            return Response(
                {"error": "You do not have permission to view staff accounts."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        allowed_roles = [User.Role.AGENT, User.Role.CARETAKER]
        if hasattr(User.Role, 'PROPERTY_MANAGER'):
            allowed_roles.append(User.Role.PROPERTY_MANAGER)
            
        queryset = User.objects.filter(
            role__in=allowed_roles
        ).select_related('profile').order_by('-date_joined')

        staff_data = []
        for u in queryset:
            staff_data.append({
                "id": u.id,
                "full_name": u.profile.full_name if u.profile else u.email.split('@')[0],
                "email": u.email,
                "phone_number": u.phone_number,
                "role": u.role,
                "is_active": u.is_active,
                "date_joined": u.date_joined.strftime('%Y-%m-%d') if u.date_joined else None,
            })
            
        return Response(staff_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['PATCH'], url_path='deactivate')
    def deactivate_staff(self, request, pk=None):
        """
        Deactivates a staff member's account, logs the reason, 
        and AUTOMATICALLY terminates all their property assignments.
        """
        if request.user.role not in [User.Role.LANDLORD, User.Role.AGENCY, User.Role.ADMIN]:
            return Response(
                {"error": "You do not have permission to deactivate staff accounts."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        try:
            staff_user = User.objects.get(id=pk)
        except User.DoesNotExist:
            return Response({"error": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)
            
        reason = request.data.get('reason', 'No reason provided.')
        
        # 1. Deactivate the user account
        staff_user.is_active = False
        staff_user.save(update_fields=['is_active'])
        
        # ✅ 2. CRITICAL FIX: Auto-terminate all active property assignments
        terminated_count = PropertyStaffAssignment.objects.filter(
            user=staff_user,
            is_active=True
        ).update(
            is_active=False, 
            terminated_at=timezone.now(),
            notes=f"Auto-terminated due to staff revocation: {reason}"
        )
        
        return Response({
            "message": f"Staff member {staff_user.email} has been successfully deactivated.",
            "reason": reason,
            "assignments_terminated": terminated_count
        }, status=status.HTTP_200_OK)

    # ✅ NEW: GET STAFF PROPERTY ASSIGNMENTS
    @action(detail=True, methods=['GET'], url_path='assignments')
    def get_staff_assignments(self, request, pk=None):
        """Fetches all active property assignments for a specific staff member."""
        if request.user.role not in [User.Role.LANDLORD, User.Role.AGENCY, User.Role.ADMIN]:
            return Response(
                {"error": "You do not have permission to view staff assignments."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        assignments = PropertyStaffAssignment.objects.filter(
            user_id=pk, 
            is_active=True
        ).select_related('property', 'assigned_by_agency').order_by('-assigned_at')
        
        data = []
        for assignment in assignments:
            data.append({
                "assignment_id": assignment.id,
                "property_id": assignment.property.id,
                "property_name": assignment.property.title,
                "operational_role": assignment.operational_role,
                "assigned_by_agency": assignment.assigned_by_agency.name if assignment.assigned_by_agency else "Direct Landlord",
                "assigned_at": assignment.assigned_at.strftime('%Y-%m-%d') if assignment.assigned_at else None
            })
        return Response(data, status=status.HTTP_200_OK)