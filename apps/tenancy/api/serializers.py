from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import Tenancy, Occupancy, TenancyNote, TenancyWaiver
from ..services import (
    TenancyService, TransferService, 
    ExtensionService, TerminationService, WaiverService
)
from ..services.tenancy_state_service import TenancyStateService

User = get_user_model()


class TenancyNoteSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = TenancyNote
        fields = ['id', 'note_type', 'content', 'is_confidential', 'created_by_email', 'created_at']
        read_only_fields = ['id', 'created_by_email', 'created_at']


class TenancySerializer(serializers.ModelSerializer):
    tenant_email = serializers.EmailField(source='tenant.email', read_only=True)
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    notes = TenancyNoteSerializer(many=True, read_only=True)
    
    available_actions = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()

    class Meta:
        model = Tenancy
        fields = [
            'id', 'tenant', 'tenant_email', 'unit', 'unit_code', 'property', 'property_title',
            'tenancy_type', 'status', 'start_date', 'end_date',
            'rent_amount', 'deposit_amount', 'service_charge_amount',
            'deposit_paid', 'deposit_waived', 'service_charge_paid', 'service_charge_waived',
            'available_actions', 'health_status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant_email', 'unit_code', 'property_title', 'created_at', 'updated_at']

    @extend_schema_field(field={"type": "array", "items": {"type": "string"}})
    def get_available_actions(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        return TenancyStateService.get_available_actions(obj, request.user)

    @extend_schema_field(field={"type": "object"})
    def get_health_status(self, obj):
        return TenancyStateService.get_tenancy_health_status(obj)

    def create(self, validated_data):
        user = self.context['request'].user
        return TenancyService.create_tenancy(
            tenant=validated_data['tenant'],
            unit=validated_data['unit'],
            property_obj=validated_data['property'],
            created_by=user,
            **{k: v for k, v in validated_data.items() if k not in ['tenant', 'unit', 'property']}
        )


class TenancyActivationSerializer(serializers.Serializer):
    mark_deposit_paid = serializers.BooleanField(default=False)
    mark_service_charge_paid = serializers.BooleanField(default=False)
    request_deposit_waiver = serializers.BooleanField(default=False)
    request_service_charge_waiver = serializers.BooleanField(default=False)
    waiver_reason = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        
        if validated_data.get('mark_deposit_paid') and not instance.deposit_paid:
            instance.deposit_paid = True
        if validated_data.get('mark_service_charge_paid') and not instance.service_charge_paid:
            instance.service_charge_paid = True
            
        instance.save(update_fields=['deposit_paid', 'service_charge_paid'])

        if validated_data.get('request_deposit_waiver') or validated_data.get('request_service_charge_waiver'):
            waiver_type = 'both' if (validated_data['request_deposit_waiver'] and validated_data['request_service_charge_waiver']) else \
                          'deposit' if validated_data['request_deposit_waiver'] else 'service_charge'
            
            waiver = TenancyWaiver.objects.create(
                tenancy=instance,
                waiver_type=waiver_type,
                reason=validated_data.get('waiver_reason', ''),
                requested_by=user
            )
            if user.role in ['landlord', 'admin', 'agency']:
                WaiverService.approve_waiver(waiver, approved_by=user)

        if instance.status == 'pending_payment' and instance.is_ready_for_activation():
            return TenancyService.activate_tenancy(instance, activated_by=user)
            
        return instance


class TenancyTransferSerializer(serializers.Serializer):
    to_unit_id = serializers.IntegerField()
    reason = serializers.CharField()

    def create(self, validated_data):
        user = self.context['request'].user
        tenancy = self.context['tenancy']
        return TransferService.create_transfer(
            tenancy=tenancy,
            to_unit_id=validated_data['to_unit_id'],
            reason=validated_data['reason'],
            requested_by=user
        )


class TenancyExtensionSerializer(serializers.Serializer):
    new_end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        user = self.context['request'].user
        tenancy = self.context['tenancy']
        return ExtensionService.create_extension(
            tenancy=tenancy,
            new_end_date=validated_data['new_end_date'],
            reason=validated_data.get('reason', ''),
            requested_by=user
        )


class TenancyTerminationSerializer(serializers.Serializer):
    termination_type = serializers.ChoiceField(choices=['tenant_request', 'landlord_request', 'breach', 'expiry'])
    notes = serializers.CharField(required=False, allow_blank=True)
    penalty_applied = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def create(self, validated_data):
        user = self.context['request'].user
        tenancy = self.context['tenancy']
        return TerminationService.terminate_tenancy(
            tenancy=tenancy,
            termination_type=validated_data['termination_type'],
            notes=validated_data.get('notes', ''),
            penalty_applied=validated_data.get('penalty_applied'),
            approved_by=user
        )


class TenancyWaiverSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenancyWaiver
        # ✅ FIX: Removed 'amount' and 'created_at' as they do not exist on the TenancyWaiver model
        fields = ['id', 'waiver_type', 'reason', 'status', 'requested_by', 'approved_by']
        read_only_fields = ['id', 'status', 'approved_by']


class OccupancySerializer(serializers.ModelSerializer):
    tenant_email = serializers.EmailField(source='current_tenant.email', read_only=True, allow_null=True)
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)

    class Meta:
        model = Occupancy
        fields = ['unit', 'unit_code', 'is_occupied', 'current_tenant', 'tenant_email', 
                  'occupancy_start_date', 'occupancy_end_date', 'updated_at']
        read_only_fields = fields