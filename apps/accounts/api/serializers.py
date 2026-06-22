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
    
    # ✅ FIX: Make username completely optional for the frontend
    username = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'phone_number', 'password', 'role']
        extra_kwargs = {
            'email': {'required': True},
        }

    def validate_email(self, value):
        # ✅ Force lowercase and strip spaces before checking existence
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # ✅ Clean data
        email = validated_data.pop('email').strip().lower()
        password = validated_data.pop('password')
        phone = validated_data.get('phone_number', '').strip()
        
        # ✅ HANDLE OPTIONAL USERNAME:
        # If the frontend didn't send a username, but the database model requires one,
        # we auto-generate a unique username from the email address.
        username = validated_data.pop('username', '').strip()
        if not username and getattr(User, 'USERNAME_FIELD', None) == 'username':
            username = email.split('@')[0] # e.g., 'fred' from 'fred@gmail.com'
            base_username = username
            counter = 1
            # Ensure the generated username is unique
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
        
        # Prepare kwargs for create_user
        create_kwargs = validated_data.copy()
        if getattr(User, 'USERNAME_FIELD', None) == 'username':
            create_kwargs['username'] = username
        else:
            # If the model uses 'email' as the primary field, remove username entirely
            create_kwargs.pop('username', None)

        # Create the user with hashed password
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
    role = serializers.CharField()
    next_route = serializers.CharField(help_text="The exact frontend route the user should be redirected to.")
    message = serializers.CharField(help_text="Human-readable message explaining the redirection.")