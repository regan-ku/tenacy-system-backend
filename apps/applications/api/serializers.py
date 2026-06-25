from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from apps.properties.models.unit import Unit

from ..models import Application, ApplicationNote
# ✅ FIX: Import NotesService so we can safely save the applicant's notes
from ..services import ApplicationService, ApprovalService, NotesService 

User = get_user_model()


class ApplicationNoteSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing and creating notes on an application.
    """
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)

    class Meta:
        model = ApplicationNote
        fields = ['id', 'note_type', 'content', 'is_confidential', 'created_by_email', 'created_at']
        read_only_fields = ['id', 'created_by_email', 'created_at']


class ApplicationDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for viewing an application, including nested notes 
    and reviewer context for agents/managers.
    """
    applicant_email = serializers.EmailField(source='applicant.email', read_only=True)
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True, allow_null=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    notes = ApplicationNoteSerializer(many=True, read_only=True)
    
    # Dynamic reviewer context (only populated for Agents/Managers/Landlords)
    reviewer_context = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'applicant', 'applicant_email', 'property', 'property_title', 
            'unit', 'unit_code', 'application_type', 'status', 'created_at', 
            'updated_at', 'notes', 'reviewer_context'
        ]
        read_only_fields = [
            'id', 'applicant', 'applicant_email', 'property_title', 'unit_code', 
            'status', 'created_at', 'updated_at'
        ]

    @extend_schema_field(field={"type": "object", "nullable": True})
    def get_reviewer_context(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
            
        # Only Agents, Managers, Landlords, and Admins get the screening context
        if request.user.role in ['agent', 'manager', 'landlord', 'admin', 'agency']:
            return ApprovalService.get_reviewer_context(obj, request.user)
        return None


class RentalApplicationCreateSerializer(serializers.Serializer):
    target_unit_id = serializers.IntegerField()
    employment_status = serializers.CharField(max_length=100)
    anticipated_move_in_date = serializers.DateField()
    
    notes = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_target_unit_id(self, value):
        try:
            unit = Unit.objects.get(id=value)
        except Unit.DoesNotExist:
            raise serializers.ValidationError("The selected unit does not exist.")
        
        if unit.status != 'available':
            raise serializers.ValidationError("This unit is no longer available for applications.")
            
        return value

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        
        unit = Unit.objects.get(id=validated_data['target_unit_id'])
        
        # 1. Create the core application via the service
        application = ApplicationService.create_rental_application(
            applicant=user,
            unit=unit,
            employment_status=validated_data['employment_status'],
            desired_move_in_date=validated_data['anticipated_move_in_date']
        )
        
        # ✅ CRITICAL FIX: The Application model does NOT have a 'message' field.
        # Instead of crashing, we save the frontend's 'notes' as an ApplicationNote.
        # This perfectly aligns with your ApplicationDetailSerializer which expects a 'notes' array.
        notes_content = validated_data.get('notes')
        if notes_content:
            NotesService.create_note(
                application=application,
                user=user,
                content=notes_content,
                note_type='applicant_note', # Categorized as a note from the applicant
                is_confidential=False
            )
            
        return application


class TransferApplicationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a transfer application for an existing tenant.
    """
    to_unit_id = serializers.IntegerField()
    reason = serializers.CharField()

    def create(self, validated_data):
        user = self.context['request'].user
        from apps.properties.models import Unit
        from apps.tenancy.models import Tenancy
        
        to_unit = Unit.objects.get(id=validated_data['to_unit_id'])
        current_tenancy = Tenancy.objects.filter(tenant=user, status__in=['active', 'extended']).first()
        
        if not current_tenancy:
            raise serializers.ValidationError("You must have an active tenancy to request a transfer.")

        return ApplicationService.create_transfer_application(
            applicant=user,
            current_tenancy=current_tenancy,
            to_unit=to_unit,
            reason=validated_data['reason']
        )


class EvictionApplicationCreateSerializer(serializers.Serializer):
    """
    Serializer for a tenant-initiated notice to vacate (eviction/move-out).
    """
    unit_id = serializers.IntegerField()
    notice_period_days = serializers.IntegerField(min_value=1)
    intended_vacate_date = serializers.DateField()
    reason_for_leaving = serializers.CharField(required=False, allow_blank=True)
    forwarding_address = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        user = self.context['request'].user
        from apps.properties.models import Unit
        
        unit = Unit.objects.get(id=validated_data['unit_id'])
        
        return ApplicationService.create_eviction_application(
            applicant=user,
            unit=unit,
            notice_period_days=validated_data['notice_period_days'],
            intended_vacate_date=validated_data['intended_vacate_date'],
            reason_for_leaving=validated_data.get('reason_for_leaving', ''),
            forwarding_address=validated_data.get('forwarding_address', '')
        )


class ApplicationDecisionSerializer(serializers.Serializer):
    """
    Serializer for Agents/Managers to approve, reject, or escalate an application.
    """
    decision = serializers.ChoiceField(choices=['approved', 'rejected', 'escalated'])
    reason = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        return ApprovalService.process_decision(
            application=instance,
            decision=validated_data['decision'],
            reviewer=user,
            reason=validated_data.get('reason', '')
        )