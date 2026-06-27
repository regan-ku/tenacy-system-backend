import json
from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from django.utils import timezone

from ..models import Tenancy, Occupancy, TenancyNote, TenancyWaiver, TenancyTransfer, TenancyExtension, TenancyTermination
from ..services import (
    TenancyService, TransferService, 
    ExtensionService, TerminationService, WaiverService
)
from ..services.tenancy_state_service import TenancyStateService

User = get_user_model()


class TenancyNoteSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    tenancy_id = serializers.IntegerField(source='tenancy.id', read_only=True)

    class Meta:
        model = TenancyNote
        fields = ['id', 'tenancy_id', 'note_type', 'content', 'is_confidential', 'created_by_email', 'created_at']
        read_only_fields = ['id', 'tenancy_id', 'created_by_email', 'created_at']


class TenancySerializer(serializers.ModelSerializer):
    tenant_email = serializers.EmailField(source='tenant.email', read_only=True)
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    
    notes = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()
    pending_requests = serializers.SerializerMethodField()

    class Meta:
        model = Tenancy
        fields = [
            'id', 'tenant', 'tenant_email', 'unit', 'unit_code', 'property', 'property_title',
            'tenancy_type', 'status', 'start_date', 'end_date',
            'rent_amount', 'deposit_amount', 'service_charge_amount',
            'deposit_paid', 'deposit_waived', 'service_charge_paid', 'service_charge_waived',
            'available_actions', 'health_status', 'notes', 'pending_requests', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant_email', 'unit_code', 'property_title', 'created_at', 'updated_at']

    def get_notes(self, obj):
        """Explicitly fetch notes to ensure they are always visible to managers."""
        notes = TenancyNote.objects.filter(tenancy=obj).order_by('-created_at')
        return TenancyNoteSerializer(notes, many=True, context=self.context).data

    @extend_schema_field(field={"type": "array", "items": {"type": "string"}})
    def get_available_actions(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        return TenancyStateService.get_available_actions(obj, request.user)

    @extend_schema_field(field={"type": "object"})
    def get_health_status(self, obj):
        return TenancyStateService.get_tenancy_health_status(obj)

    @extend_schema_field(field={"type": "object", "nullable": True})
    def get_pending_requests(self, obj):
        """
        ✅ FIXED: Now queries the unified Application model.
        Uses property_ref instead of property to match the Unit model.
        """
        from apps.applications.models import Application
        from apps.properties.models import Unit
        
        pending = {}
        
        def parse_note(app, prefix):
            note = app.notes.filter(content__startswith=prefix).first()
            if note:
                try:
                    json_str = note.content.replace(prefix, '')
                    return json.loads(json_str)
                except Exception:
                    return {}
            return {}

        # 1. TRANSFER application
        pending_transfer_app = Application.objects.filter(
            applicant=obj.tenant,
            unit=obj.unit,
            application_type='transfer',
            status__in=['pending', 'under_review', 'escalated']
        ).first()
        
        if pending_transfer_app:
            data = parse_note(pending_transfer_app, 'TRANSFER_REQUEST:')
            if data:
                # ✅ FIXED: Use select_related('property_ref') and property_ref
                to_unit = Unit.objects.select_related('property_ref').filter(id=data.get('to_unit')).first()
                pending['transfer'] = {
                    'id': pending_transfer_app.id,
                    'application_id': pending_transfer_app.id,
                    'to_unit': to_unit.unit_code if to_unit else 'N/A',
                    # ✅ FIXED: Use property_ref instead of property
                    'to_property': to_unit.property_ref.title if to_unit and to_unit.property_ref else 'Unknown',
                    'move_in_date': data.get('desired_move_in_date'),
                    'reason': data.get('reason', ''),
                    'status': pending_transfer_app.status
                }

        # 2. TERMINATION application
        pending_term_app = Application.objects.filter(
            applicant=obj.tenant,
            unit=obj.unit,
            application_type='termination',
            status__in=['pending', 'under_review', 'escalated']
        ).first()
        
        if pending_term_app:
            data = parse_note(pending_term_app, 'TERMINATION_REQUEST:')
            if data:
                pending['termination'] = {
                    'id': pending_term_app.id,
                    'application_id': pending_term_app.id,
                    'effective_date': data.get('date'),
                    'termination_type': 'tenant_request',
                    'notes': data.get('reason', ''),
                    'status': pending_term_app.status
                }

        # 3. EXTENSION application
        pending_ext_app = Application.objects.filter(
            applicant=obj.tenant,
            unit=obj.unit,
            application_type='extension',
            status__in=['pending', 'under_review', 'escalated']
        ).first()
        
        if pending_ext_app:
            data = parse_note(pending_ext_app, 'EXTENSION_REQUEST:')
            if data:
                pending['extension'] = {
                    'id': pending_ext_app.id,
                    'application_id': pending_ext_app.id,
                    'new_end_date': data.get('new_end_date'),
                    'reason': data.get('reason', ''),
                    'status': pending_ext_app.status
                }
            else:
                pending_extension = TenancyExtension.objects.filter(tenancy=obj, status='pending').first()
                if pending_extension:
                    pending['extension'] = {
                        'id': pending_extension.id,
                        'new_end_date': str(pending_extension.requested_new_end_date),
                        'reason': pending_extension.reason,
                        'status': pending_extension.status
                    }
        else:
            pending_extension = TenancyExtension.objects.filter(tenancy=obj, status='pending').first()
            if pending_extension:
                pending['extension'] = {
                    'id': pending_extension.id,
                    'new_end_date': str(pending_extension.requested_new_end_date),
                    'reason': pending_extension.reason,
                    'status': pending_extension.status
                }
        
        return pending if pending else None

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
    move_in_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_to_unit_id(self, value):
        from apps.properties.models import Unit
        try:
            unit = Unit.objects.get(id=value)
        except Unit.DoesNotExist:
            raise serializers.ValidationError("Target unit does not exist.")
        
        from ..services.validation_service import TenancyValidationService
        TenancyValidationService.validate_unit_availability(unit)
        
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        tenancy = self.context['tenancy']
        
        from apps.properties.models import Unit
        to_unit = Unit.objects.select_related('property_ref').get(id=validated_data['to_unit_id'])
        
        transfer = TenancyTransfer.objects.create(
            tenant=tenancy.tenant,
            from_property=tenancy.property,
            from_unit=tenancy.unit,
            to_property=to_unit.property_ref,
            to_unit=to_unit,
            reason=validated_data['reason'],
            requested_move_in_date=validated_data.get('move_in_date'),
            manager_notes=validated_data.get('notes', ''),
            requested_by=user,
            transfer_status='pending'
        )
        
        return transfer

class TenancyExtensionSerializer(serializers.Serializer):
    new_end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate_new_end_date(self, value):
        tenancy = self.context.get('tenancy')
        
        if not tenancy or not tenancy.end_date:
            raise serializers.ValidationError("Cannot extend a tenancy without an end date.")
        
        if value <= timezone.now().date():
            raise serializers.ValidationError("New end date must be in the future.")
        
        if value <= tenancy.end_date:
            raise serializers.ValidationError("New end date must be after the current end date.")
        
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        tenancy = self.context['tenancy']
        
        extension = TenancyExtension.objects.create(
            tenancy=tenancy,
            requested_new_end_date=validated_data['new_end_date'],
            reason=validated_data.get('reason', ''),
            requested_by=user,
            status='pending'
        )
        
        return extension


class TenancyTerminationSerializer(serializers.Serializer):
    termination_type = serializers.ChoiceField(choices=['tenant_request', 'landlord_request', 'breach', 'expiry', 'mutual'])
    notes = serializers.CharField(required=False, allow_blank=True)
    penalty_applied = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    effective_date = serializers.DateField(required=False)

    def validate(self, data):
        tenancy = self.context.get('tenancy')
        
        if tenancy and tenancy.status in [Tenancy.Status.TERMINATED, Tenancy.Status.EXPIRED]:
            raise serializers.ValidationError(f"Cannot terminate a tenancy with status '{tenancy.status}'.")
        
        if not data.get('effective_date'):
            data['effective_date'] = timezone.now().date()
        
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        tenancy = self.context['tenancy']
        
        termination = TenancyTermination.objects.create(
            tenancy=tenancy,
            termination_type=validated_data['termination_type'],
            notes=validated_data.get('notes', ''),
            penalty_applied=validated_data.get('penalty_applied', 0),
            effective_date=validated_data['effective_date'],
            approved_by=user
        )
        
        return termination


class TenancyWaiverSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenancyWaiver
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