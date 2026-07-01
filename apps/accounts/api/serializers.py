from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import Profile, NextOfKin, Verification
from ..services import UserService, VerificationService

User = get_user_model()

# ==========================================
# 1. REGISTRATION & AUTH
# ==========================================
class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for creating a new user account."""
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    phone_number = serializers.CharField(max_length=20)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.TENANT)
    
    username = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'phone_number', 'password', 'role']
        extra_kwargs = {
            'email': {'required': True},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        email = validated_data.pop('email').strip().lower()
        password = validated_data.pop('password')
        phone = validated_data.get('phone_number', '').strip()
        
        username = validated_data.pop('username', '').strip()
        if not username and getattr(User, 'USERNAME_FIELD', None) == 'username':
            username = email.split('@')[0] 
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
        
        create_kwargs = validated_data.copy()
        if getattr(User, 'USERNAME_FIELD', None) == 'username':
            create_kwargs['username'] = username
        else:
            create_kwargs.pop('username', None)

        user = User.objects.create_user(
            email=email,
            password=password,
            **create_kwargs
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login request body."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# ==========================================
# 2. PROFILE & ROLE UPGRADE
# ==========================================
class RoleUpgradeSerializer(serializers.Serializer):
    """Serializer to handle a user's request to upgrade their operational role."""
    target_role = serializers.ChoiceField(
        choices=[User.Role.LANDLORD, User.Role.AGENCY],
        help_text="The role you wish to upgrade to (LANDLORD or AGENCY)."
    )

    def validate_target_role(self, value):
        user = self.context['request'].user
        if user.role == value:
            raise serializers.ValidationError(f"You are already a {value}.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        return UserService.request_role_upgrade(user, validated_data['target_role'])


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for User Profile. Enforces National ID requirement ONLY for Landlords."""
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'full_name', 'national_id', 'nationality', 'address', 
            'date_of_birth', 'profile_photo', 'profile_complete', 
            'email', 'phone_number', 'role'
        ]
        extra_kwargs = {
            'profile_photo': {'help_text': 'Optional profile picture upload.'},
            'national_id': {'help_text': 'Mandatory for Landlords. Optional for Tenants. Not required for Agencies.'}
        }

    @extend_schema_field(
        field={
            "type": "string",
            "enum": [choice[0] for choice in User.Role.choices],
            "description": "The user's current system role."
        }
    )
    def get_role(self, obj):
        return obj.user.role

    def validate_national_id(self, value):
        user = self.context['request'].user
        if user.role == User.Role.LANDLORD and not value:
            raise serializers.ValidationError("National ID is mandatory for Landlords.")
        return value

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.save()
        return instance

# ==========================================
# 3. NEXT OF KIN
# ==========================================
class NextOfKinSerializer(serializers.ModelSerializer):
    class Meta:
        model = NextOfKin
        fields = ['id', 'full_name', 'relationship', 'phone_number', 'city', 'is_primary']
        extra_kwargs = {
            'phone_number': {'help_text': 'Format: +254712345678 or 0712345678'}
        }

    def create(self, validated_data):
        user = self.context['request'].user
        return UserService.add_next_of_kin(user, validated_data)


# ==========================================
# 4. VERIFICATION (UPDATED WITH AGENCY DOCS)
# ==========================================
class VerificationSerializer(serializers.ModelSerializer):
    """Serializer for submitting verification documents (multipart/form-data)."""
    class Meta:
        model = Verification
        fields = [
            'id', 
            'id_document_front', 'id_document_back', 
            'kra_pin', 'kra_tax_compliance_cert', 
            'business_registration', 'agency_license',
            'status', 'rejection_reason'
        ]
        read_only_fields = ['id', 'status', 'rejection_reason']
        extra_kwargs = {
            'id_document_front': {'help_text': 'Front side of National ID (Required for Landlords).'},
            'id_document_back': {'help_text': 'Back side of National ID (Required for Landlords).'},
            'kra_pin': {'help_text': 'Format: A012345678B'},
            'kra_tax_compliance_cert': {'help_text': 'Valid KRA Tax Compliance Certificate.'},
            'business_registration': {'help_text': 'Business Registration Certificate (Required for Agencies).'},
            'agency_license': {'help_text': 'EARB Agency License (Required for Agencies).'},
        }

    def update(self, instance, validated_data):
        user = self.context['request'].user
        files = self.context['request'].FILES
        return VerificationService.submit_verification(user, validated_data, files)


# ==========================================
# 5. USER STATE RESPONSE
# ==========================================
class UserStateResponseSerializer(serializers.Serializer):
    """Defines the exact shape of the Post-Login User State Resolution Engine response."""
    profile_complete = serializers.BooleanField()
    tenant_profile_complete = serializers.BooleanField(required=False, default=True) 
    role = serializers.CharField()
    next_route = serializers.CharField(help_text="The exact frontend route the user should be redirected to.")
    message = serializers.CharField(help_text="Human-readable message explaining the redirection.")


# ==========================================
# 6. SMART LOOKUP, STAFF & TENANT CREATION
# ==========================================
class LookupApplicantSerializer(serializers.Serializer):
    """Validates input for the Smart Lookup API."""
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=25, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise serializers.ValidationError("Either email or phone number is required.")
        return attrs

class StaffCreateSerializer(serializers.Serializer):
    """Validates input for creating a Staff member (Ghost Profile)."""
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=25, required=False, allow_blank=True)
    
    # ✅ FIXED: Explicitly allow 'property_manager' even though it's not a User.Role
    role = serializers.ChoiceField(
        choices=[
            (User.Role.AGENT, 'Agent'), 
            (User.Role.CARETAKER, 'Caretaker'), 
            ('property_manager', 'Property Manager')
        ]
    )

    def create(self, validated_data):
        manager_user = self.context['request'].user
        
        # Permission check: Only managers, landlords, agencies, or admins can do this
        allowed_roles = [User.Role.LANDLORD, User.Role.AGENCY, User.Role.AGENT, User.Role.ADMIN]
            
        if manager_user.role not in allowed_roles:
            raise serializers.ValidationError("You do not have permission to create staff accounts.")
            
        return UserService.create_staff_for_manager(manager_user, validated_data)

class TenantIdentitySerializer(serializers.Serializer):
    """Validates the core login credentials for a new/existing tenant."""
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=25, required=False, allow_blank=True)

class TenantProfileDataSerializer(serializers.Serializer):
    """Validates the profile information for the new/existing tenant."""
    full_name = serializers.CharField(max_length=255)
    national_id = serializers.CharField(max_length=8, required=False, allow_blank=True)
    nationality = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

class TenantNextOfKinDataSerializer(serializers.Serializer):
    """Validates the emergency contact information for the new/existing tenant."""
    full_name = serializers.CharField(max_length=255)
    relationship = serializers.ChoiceField(choices=NextOfKin.RELATIONSHIP_CHOICES)
    phone_number = serializers.CharField(max_length=15)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)

class ManagerCreateTenantSerializer(serializers.Serializer):
    """
    Master serializer for the 'Add Tenant' modal.
    Orchestrates the creation OR UPDATE of User, Profile, and NextOfKin via UserService.
    """
    tenant_data = TenantIdentitySerializer()
    profile_data = TenantProfileDataSerializer()
    next_of_kin_data = TenantNextOfKinDataSerializer(required=False, allow_null=True)

    def create(self, validated_data):
        manager_user = self.context['request'].user
        
        allowed_roles = [User.Role.LANDLORD, User.Role.AGENCY, User.Role.AGENT, User.Role.ADMIN]
            
        if manager_user.role not in allowed_roles:
            raise serializers.ValidationError("You do not have permission to manage tenant accounts.")
            
        return UserService.create_or_update_tenant_for_manager(manager_user, validated_data)