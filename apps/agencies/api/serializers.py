from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from ..models import (
    Agency, AgencyDirector, AgencyVerification, AgencyProfile, 
    AgencyStaff, DelegatedProperty
)
from ..services import (
    AgencyService, DirectorService, AgencyVerificationService, 
    AgencyProfileService, StaffService, DelegationService
)


class AgencySerializer(serializers.ModelSerializer):
    """
    Basic serializer for creating and listing agencies.
    """
    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'registration_number', 'contact_email', 'phone_number', 
            'physical_address', 'status', 'is_active', 'created_at'
        ]
        read_only_fields = ['status', 'is_active', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        return AgencyService.create_agency(
            created_by_user=user,
            name=validated_data['name'],
            registration_number=validated_data['registration_number'],
            contact_email=validated_data['contact_email'],
            phone_number=validated_data['phone_number'],
            physical_address=validated_data['physical_address']
        )


class AgencyProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the Agency's Business Profile.
    """
    class Meta:
        model = AgencyProfile
        fields = [
            'id', 'business_name', 'registration_number', 'kra_pin', 'physical_address', 
            'postal_code', 'city', 'county', 'contact_person_name', 'contact_person_phone', 
            'contact_person_email', 'is_profile_complete'
        ]

    def validate_registration_number(self, value):
        agency = self.context.get('agency')
        if agency and value != agency.registration_number:
            raise serializers.ValidationError("Profile registration number must match the agency's official registration number.")
        return value

    def update(self, instance, validated_data):
        agency = self.context.get('agency') or instance.agency
        return AgencyProfileService.create_or_update_profile(agency=agency, profile_data=validated_data)


class AgencyDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for retrieving a single agency.
    THIS IS WHERE AGENCY PROFILE IS USED: It is nested for read operations.
    """
    profile = AgencyProfileSerializer(source='business_profile', read_only=True)
    
    # ✅ CRITICAL FIX: Explicitly declare these as SerializerMethodFields 
    # so DRF doesn't look for them as database columns on the Agency model.
    directors_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'registration_number', 'contact_email', 'phone_number', 
            'physical_address', 'status', 'is_active', 'created_at', 
            'profile', 'directors_count', 'staff_count'
        ]

    @extend_schema_field(field={"type": "integer"})
    def get_directors_count(self, obj):
        return obj.directors.count()

    @extend_schema_field(field={"type": "integer"})
    def get_staff_count(self, obj):
        return obj.staff_members.filter(status='active').count()


class AgencyDirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyDirector
        fields = [
            'id', 'user', 'full_name', 'national_id', 'passport_number', 
            'email', 'phone_number', 'nationality', 'address', 
            'ownership_percentage', 'is_primary_director', 'verification_status'
        ]

    def validate(self, data):
        if not data.get('national_id') and not data.get('passport_number'):
            raise serializers.ValidationError("Either National ID or Passport Number is required.")
        return data

    def create(self, validated_data):
        agency = self.context['agency']
        user = self.context['request'].user
        return DirectorService.add_director(agency=agency, created_by_user=user, **validated_data)


class AgencyVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyVerification
        fields = [
            'id', 'business_registration_cert', 'kra_pin', 'kra_tax_compliance_cert', 
            'agency_license', 'status', 'rejection_reason'
        ]
        read_only_fields = ['id', 'status', 'rejection_reason']

    def update(self, instance, validated_data):
        user = self.context['request'].user
        files = self.context['request'].FILES
        return AgencyVerificationService.submit_business_verification(
            agency=instance.agency, submitted_by_user=user, data=validated_data, files=files
        )


class AgencyStaffSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = AgencyStaff
        fields = ['id', 'user', 'user_email', 'role', 'status', 'contact_phone', 'contact_email', 'joined_at']

    def create(self, validated_data):
        agency = self.context['agency']
        user = self.context['request'].user
        return StaffService.create_staff_member(
            agency=agency, created_by_user=user, user=validated_data['user'],
            role=validated_data['role'], contact_phone=validated_data.get('contact_phone'),
            contact_email=validated_data.get('contact_email')
        )


class DelegatedPropertySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source='property_ref.title', read_only=True)
    
    class Meta:
        model = DelegatedProperty
        fields = ['id', 'property_ref', 'property_name', 'delegation_type', 'custom_permissions', 'status', 'start_date', 'end_date']

    def create(self, validated_data):
        agency = self.context['agency']
        user = self.context['request'].user
        return DelegationService.landlord_delegates_property(
            landlord_user=user, agency=agency, property_ref=validated_data['property_ref'],
            delegation_type=validated_data['delegation_type'], start_date=validated_data['start_date'],
            end_date=validated_data.get('end_date'), custom_permissions=validated_data.get('custom_permissions', {})
        )