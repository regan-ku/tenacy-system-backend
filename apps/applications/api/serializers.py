import json
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field

from apps.properties.models.unit import Unit
from ..models import Application, ApplicationNote
from ..services import ApplicationService, ApprovalService, NotesService 

User = get_user_model()

class ApplicationNoteSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)

    class Meta:
        model = ApplicationNote
        fields = ['id', 'note_type', 'content', 'is_confidential', 'created_by_email', 'created_at']
        read_only_fields = ['id', 'created_by_email', 'created_at']

class ApplicationDetailSerializer(serializers.ModelSerializer):
    applicant_email = serializers.EmailField(source='applicant.email', read_only=True)
    applicant_name = serializers.SerializerMethodField()
    applicant_phone = serializers.SerializerMethodField()
    
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True, allow_null=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    notes = ApplicationNoteSerializer(many=True, read_only=True)
    financial_status = serializers.SerializerMethodField()
    reviewer_context = serializers.SerializerMethodField()

    # Transfer fields
    from_property_name = serializers.SerializerMethodField()
    from_unit_code = serializers.SerializerMethodField()
    to_property_name = serializers.SerializerMethodField()
    to_unit_code = serializers.SerializerMethodField()
    desired_move_in_date = serializers.SerializerMethodField()
    transfer_reason = serializers.SerializerMethodField()

    # Termination fields
    proposed_move_out_date = serializers.SerializerMethodField()
    termination_type = serializers.SerializerMethodField()
    penalty_amount = serializers.SerializerMethodField()
    termination_notes = serializers.SerializerMethodField()

    # Extension fields
    new_end_date = serializers.SerializerMethodField()
    extension_reason = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'applicant', 'applicant_name', 'applicant_phone', 'applicant_email', 
            'property', 'property_title', 'unit', 'unit_code', 'application_type', 'status', 
            'created_at', 'updated_at', 'notes', 'financial_status', 'reviewer_context',
            'from_property_name', 'from_unit_code', 'to_property_name', 'to_unit_code',
            'desired_move_in_date', 'transfer_reason',
            'proposed_move_out_date', 'termination_type', 'penalty_amount', 'termination_notes',
            'new_end_date', 'extension_reason'
        ]
        read_only_fields = ['id', 'applicant', 'applicant_name', 'applicant_phone', 'applicant_email', 
                           'property_title', 'unit_code', 'status', 'created_at', 'updated_at']

    def get_applicant_name(self, obj):
        if hasattr(obj, 'full_name') and obj.full_name:
            return obj.full_name
        if obj.applicant:
            profile = getattr(obj.applicant, 'profile', None)
            if profile and hasattr(profile, 'full_name') and profile.full_name: 
                return profile.full_name
            return obj.applicant.email
        return "Unknown Applicant"

    def get_applicant_phone(self, obj):
        if hasattr(obj, 'phone_number') and obj.phone_number:
            return obj.phone_number
        if obj.applicant:
            profile = getattr(obj.applicant, 'profile', None)
            if profile:
                phone = getattr(profile, 'phone_number', None) or getattr(profile, 'phone', None)
                if phone:
                    return phone
            user_phone = getattr(obj.applicant, 'phone', None) or getattr(obj.applicant, 'phone_number', None)
            if user_phone:
                return user_phone
        return "N/A"

    def _parse_transfer_details(self, obj):
        from_unit = obj.unit
        from_property = obj.property
        
        note = obj.notes.filter(content__startswith='TRANSFER_REQUEST:').first()
        if not note: 
            return {
                'from_property_name': from_property.title if from_property else 'Unknown',
                'from_unit_code': from_unit.unit_code if from_unit else 'N/A',
                'to_property_name': 'Unknown', 'to_unit_code': 'N/A', 'to_unit_id': None,
                'transfer_reason': '', 'desired_move_in_date': None, 'notes': ''
            }
        try:
            json_str = note.content.replace('TRANSFER_REQUEST:', '')
            data = json.loads(json_str)
            
            to_unit_id = data.get('to_unit')
            to_unit = Unit.objects.select_related('property_ref').filter(id=to_unit_id).first() if to_unit_id else None
            
            return {
                'from_property_name': from_property.title if from_property else 'Unknown',
                'from_unit_code': from_unit.unit_code if from_unit else 'N/A',
                'to_property_name': to_unit.property_ref.title if to_unit and to_unit.property_ref else 'Unknown',
                'to_unit_code': to_unit.unit_code if to_unit else 'N/A',
                'to_unit_id': to_unit.id if to_unit else None,
                'transfer_reason': data.get('reason', ''),
                'desired_move_in_date': data.get('desired_move_in_date'),
                'notes': data.get('notes', '')
            }
        except Exception as e:
            print(f"Error parsing transfer note: {e}")
            return {
                'from_property_name': from_property.title if from_property else 'Unknown',
                'from_unit_code': from_unit.unit_code if from_unit else 'N/A',
                'to_property_name': 'Unknown', 'to_unit_code': 'N/A', 'to_unit_id': None,
                'transfer_reason': '', 'desired_move_in_date': None, 'notes': ''
            }

    def _get_parsed_transfer(self, obj):
        if not hasattr(obj, '_parsed_transfer'): 
            obj._parsed_transfer = self._parse_transfer_details(obj)
        return obj._parsed_transfer

    def get_from_property_name(self, obj): return self._get_parsed_transfer(obj).get('from_property_name')
    def get_from_unit_code(self, obj): return self._get_parsed_transfer(obj).get('from_unit_code')
    def get_to_property_name(self, obj): return self._get_parsed_transfer(obj).get('to_property_name')
    def get_to_unit_code(self, obj): return self._get_parsed_transfer(obj).get('to_unit_code')
    def get_desired_move_in_date(self, obj): return self._get_parsed_transfer(obj).get('desired_move_in_date')
    def get_transfer_reason(self, obj): return self._get_parsed_transfer(obj).get('transfer_reason')

    def _parse_termination_details(self, obj):
        note = obj.notes.filter(content__startswith='TERMINATION_REQUEST:').first()
        if not note: return {}
        try:
            json_str = note.content.replace('TERMINATION_REQUEST:', '')
            data = json.loads(json_str)
            return {
                'proposed_move_out_date': data.get('date', ''),
                'termination_type': 'tenant_request', 
                'penalty_amount': float(data.get('penalty', 0)),
                'termination_notes': data.get('reason', '')
            }
        except Exception: return {}

    def _get_parsed_termination(self, obj):
        if not hasattr(obj, '_parsed_termination'): 
            obj._parsed_termination = self._parse_termination_details(obj)
        return obj._parsed_termination

    def get_proposed_move_out_date(self, obj): return self._get_parsed_termination(obj).get('proposed_move_out_date')
    def get_termination_type(self, obj): return self._get_parsed_termination(obj).get('termination_type')
    def get_penalty_amount(self, obj): return self._get_parsed_termination(obj).get('penalty_amount')
    def get_termination_notes(self, obj): return self._get_parsed_termination(obj).get('termination_notes')

    def _parse_extension_details(self, obj):
        note = obj.notes.filter(content__startswith='EXTENSION_REQUEST:').first()
        if not note: return {}
        try:
            json_str = note.content.replace('EXTENSION_REQUEST:', '')
            data = json.loads(json_str)
            return {
                'new_end_date': data.get('new_end_date', ''),
                'extension_reason': data.get('reason', '')
            }
        except Exception: return {}

    def _get_parsed_extension(self, obj):
        if not hasattr(obj, '_parsed_extension'): 
            obj._parsed_extension = self._parse_extension_details(obj)
        return obj._parsed_extension

    def get_new_end_date(self, obj): return self._get_parsed_extension(obj).get('new_end_date')
    def get_extension_reason(self, obj): return self._get_parsed_extension(obj).get('extension_reason')

    def get_financial_status(self, obj):
        from apps.tenancy.models import Tenancy
        target_unit = obj.unit
        if obj.application_type == 'transfer':
            parsed = self._get_parsed_transfer(obj)
            to_unit_id = parsed.get('to_unit_id')
            if to_unit_id: 
                target_unit = Unit.objects.filter(id=to_unit_id).first() or obj.unit

        tenancy = Tenancy.objects.filter(
            tenant=obj.applicant, unit=target_unit, 
            status__in=['pending_payment', 'active', 'scheduled_for_termination']
        ).first()
        if tenancy:
            return {
                "rent_amount": float(tenancy.rent_amount or 0), 
                "deposit_amount": float(tenancy.deposit_amount or 0),
                "service_charge_amount": float(tenancy.service_charge_amount or 0),
                "deposit_paid": tenancy.deposit_paid, "deposit_waived": getattr(tenancy, 'deposit_waived', False),
                "service_charge_paid": tenancy.service_charge_paid, "service_charge_waived": getattr(tenancy, 'service_charge_waived', False),
                "rent_paid": getattr(tenancy, 'rent_paid', False), "rent_waived": getattr(tenancy, 'rent_waived', False),
                "tenancy_status": tenancy.status,
                "tenancy_id": tenancy.id 
            }
        return {
            "rent_amount": float(getattr(target_unit, 'rent_amount', 0) or getattr(target_unit, 'base_rent_amount', 0)),
            "deposit_amount": float(getattr(target_unit, 'deposit_amount', 0)),
            "service_charge_amount": float(getattr(target_unit, 'service_charge', 0) or getattr(target_unit, 'service_charge_amount', 0)),
            "deposit_paid": False, "deposit_waived": False, 
            "service_charge_paid": False, "service_charge_waived": False,
            "rent_paid": False, "rent_waived": False, "tenancy_status": "no_tenancy"
        }

    @extend_schema_field(field={"type": "object", "nullable": True})
    def get_reviewer_context(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated: return None
        if request.user.role in ['agent', 'manager', 'landlord', 'admin', 'agency']:
            return ApprovalService.get_reviewer_context(obj, request.user)
        return None

def resolve_applicant(attrs, request):
    applicant_id = attrs.get('applicant')
    if applicant_id:
        try: return User.objects.get(id=applicant_id)
        except User.DoesNotExist: raise serializers.ValidationError({"applicant": "Invalid tenant ID."})
    return request.user

# ==========================================
# HELPER TO MAKE QUERYDICT MUTABLE
# ==========================================
def _ensure_mutable_dict(data):
    """Converts immutable QueryDict to a standard mutable Python dict."""
    if hasattr(data, 'dict'):
        return data.dict()
    elif hasattr(data, 'copy'):
        return data.copy()
    return data


class RentalApplicationCreateSerializer(serializers.Serializer):
    application_type = serializers.CharField(default='rental', required=False)
    applicant = serializers.IntegerField(required=False)
    property = serializers.IntegerField(required=False)
    unit = serializers.IntegerField(required=False)
    target_unit_id = serializers.IntegerField(required=False)
    employment_status = serializers.CharField(max_length=100, required=False, allow_blank=True)
    anticipated_move_in_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        data = _ensure_mutable_dict(data)
        data.pop('rental_details', None)
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context['request']
        attrs['applicant_obj'] = resolve_applicant(attrs, request)
        unit_id = attrs.get('target_unit_id') or attrs.get('unit')
        if not unit_id: raise serializers.ValidationError({"target_unit_id": "Unit ID is required."})
        try: unit = Unit.objects.get(id=unit_id)
        except Unit.DoesNotExist: raise serializers.ValidationError({"target_unit_id": "Unit does not exist."})
        if unit.status != 'available': raise serializers.ValidationError({"target_unit_id": "Unit is not available."})
        
        move_in = attrs.get('anticipated_move_in_date')
        if move_in and move_in < timezone.now().date():
            raise serializers.ValidationError({"anticipated_move_in_date": "Move-in date cannot be in the past."})
            
        attrs['unit_obj'] = unit
        return attrs

    def create(self, validated_data):
        applicant = validated_data['applicant_obj']
        unit = validated_data['unit_obj']
        application = ApplicationService.create_rental_application(
            applicant=applicant, unit=unit,
            employment_status=validated_data.get('employment_status', 'employed'),
            desired_move_in_date=validated_data.get('anticipated_move_in_date') or timezone.now().date()
        )
        if validated_data.get('notes'):
            NotesService.create_note(
                application=application, user=applicant, 
                content=validated_data['notes'], note_type='applicant_note', is_confidential=False
            )
        return application

class TransferApplicationCreateSerializer(serializers.Serializer):
    application_type = serializers.CharField(default='transfer', required=False)
    applicant = serializers.IntegerField(required=False)
    property = serializers.IntegerField(required=False)
    unit = serializers.IntegerField(required=False)
    to_unit_id = serializers.IntegerField()
    reason = serializers.CharField()
    desired_move_in_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        data = _ensure_mutable_dict(data)
        if 'transfer_details' in data and isinstance(data['transfer_details'], dict):
            td = data['transfer_details']
            if 'desired_move_in_date' in td and 'desired_move_in_date' not in data:
                data['desired_move_in_date'] = td['desired_move_in_date']
            if 'notes' in td and 'notes' not in data:
                data['notes'] = td['notes']
        data.pop('transfer_details', None)
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context['request']
        applicant = resolve_applicant(attrs, request)
        attrs['applicant_obj'] = applicant
        from apps.tenancy.models import Tenancy
        unit_id = attrs.get('unit')
        if unit_id:
            current_tenancy = Tenancy.objects.filter(tenant=applicant, unit_id=unit_id, status__in=['active', 'extended']).first()
        else:
            current_tenancy = Tenancy.objects.filter(tenant=applicant, status__in=['active', 'extended']).first()
        if not current_tenancy:
            raise serializers.ValidationError("The tenant must have an active tenancy to request a transfer.")
            
        move_in = attrs.get('desired_move_in_date')
        if move_in and move_in < timezone.now().date():
            raise serializers.ValidationError({"desired_move_in_date": "Move-in date cannot be in the past."})
            
        attrs['current_tenancy'] = current_tenancy
        return attrs

    def create(self, validated_data):
        from apps.properties.models import Unit
        applicant = validated_data['applicant_obj']
        current_tenancy = validated_data['current_tenancy']
        to_unit = Unit.objects.get(id=validated_data['to_unit_id'])
        return ApplicationService.create_transfer_application(
            applicant=applicant, current_tenancy=current_tenancy, to_unit=to_unit, 
            reason=validated_data['reason'],
            desired_move_in_date=validated_data.get('desired_move_in_date'),
            notes=validated_data.get('notes', '')
        )

class EvictionApplicationCreateSerializer(serializers.Serializer):
    application_type = serializers.CharField(default='termination', required=False)
    applicant = serializers.IntegerField(required=False)
    property = serializers.IntegerField(required=False)
    unit = serializers.IntegerField(required=False)
    unit_id = serializers.IntegerField(required=False)
    notice_period_days = serializers.IntegerField(min_value=1, required=False)
    intended_vacate_date = serializers.DateField(required=False)
    reason_for_leaving = serializers.CharField(required=False, allow_blank=True)
    termination_type = serializers.CharField(required=False, default='tenant_request')
    penalty_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)

    def to_internal_value(self, data):
        data = _ensure_mutable_dict(data)
        data.pop('termination_details', None)
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context['request']
        attrs['applicant_obj'] = resolve_applicant(attrs, request)
        
        vacate = attrs.get('intended_vacate_date')
        if vacate and vacate < timezone.now().date():
            raise serializers.ValidationError({"intended_vacate_date": "Move-out date cannot be in the past."})
            
        return attrs

    def create(self, validated_data):
        from apps.properties.models import Unit
        applicant = validated_data['applicant_obj']
        unit_id = validated_data.get('unit_id') or validated_data.get('unit')
        unit = Unit.objects.get(id=unit_id)
        return ApplicationService.create_eviction_application(
            applicant=applicant, unit=unit,
            notice_period_days=validated_data.get('notice_period_days', 30),
            intended_vacate_date=validated_data.get('intended_vacate_date') or timezone.now().date(),
            reason_for_leaving=validated_data.get('reason_for_leaving', ''),
            forwarding_address=''
        )

class ExtensionApplicationCreateSerializer(serializers.Serializer):
    application_type = serializers.CharField(default='extension', required=False)
    applicant = serializers.IntegerField(required=False)
    property = serializers.IntegerField(required=False)
    unit = serializers.IntegerField(required=False)
    unit_id = serializers.IntegerField(required=False)
    new_end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def to_internal_value(self, data):
        data = _ensure_mutable_dict(data)
        if 'extension_details' in data and isinstance(data['extension_details'], dict):
            ed = data['extension_details']
            if 'new_end_date' in ed and 'new_end_date' not in data:
                data['new_end_date'] = ed['new_end_date']
            if 'reason' in ed and 'reason' not in data:
                data['reason'] = ed['reason']
        data.pop('extension_details', None)
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context['request']
        attrs['applicant_obj'] = resolve_applicant(attrs, request)
        
        new_end = attrs.get('new_end_date')
        
        if new_end and new_end <= timezone.now().date():
            raise serializers.ValidationError({"new_end_date": "New end date must be in the future."})
        
        from apps.tenancy.models import Tenancy
        applicant = attrs['applicant_obj']
        unit_id = attrs.get('unit_id') or attrs.get('unit')
        
        if unit_id:
            current_tenancy = Tenancy.objects.filter(
                tenant=applicant, unit_id=unit_id, 
                status__in=['active', 'extended']
            ).first()
        else:
            current_tenancy = Tenancy.objects.filter(
                tenant=applicant, 
                status__in=['active', 'extended']
            ).first()
        
        if not current_tenancy:
            raise serializers.ValidationError("The tenant must have an active tenancy to request an extension.")
        
        if current_tenancy.end_date and timezone.now().date() >= current_tenancy.end_date:
            raise serializers.ValidationError(
                "This tenancy period has already expired. You cannot apply for an extension. Please submit a new Rental Application instead."
            )

        if new_end and current_tenancy.end_date and new_end <= current_tenancy.end_date:
            raise serializers.ValidationError({"new_end_date": "New end date must be after the current end date."})
        
        attrs['current_tenancy'] = current_tenancy
        return attrs

    def create(self, validated_data):
        applicant = validated_data['applicant_obj']
        current_tenancy = validated_data['current_tenancy']
        return ApplicationService.create_extension_application(
            applicant=applicant,
            current_tenancy=current_tenancy,
            new_end_date=validated_data.get('new_end_date'),
            reason=validated_data.get('reason', '')
        )

class ApplicationDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['approved', 'rejected', 'escalated'])
    reason = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        return ApprovalService.process_decision(
            application=instance, decision=validated_data['decision'], 
            reviewer=user, reason=validated_data.get('reason', '')
        )

# ✅ NEW: Application Update Serializer for role-based editing
class ApplicationUpdateSerializer(serializers.Serializer):
    """
    Handles editing of Transfer, Termination, and Extension applications.
    Updates the JSON note stored in the ApplicationNote model.
    """
    # Transfer fields
    to_unit_id = serializers.IntegerField(required=False)
    desired_move_in_date = serializers.DateField(required=False, allow_null=True)
    
    # Shared fields
    reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Termination fields
    intended_vacate_date = serializers.DateField(required=False)
    penalty_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    # Extension fields
    new_end_date = serializers.DateField(required=False)

    def update(self, instance, validated_data):
        from apps.properties.models import Unit
        
        # Map application type to the correct JSON note prefix
        prefix_map = {
            'transfer': 'TRANSFER_REQUEST:',
            'termination': 'TERMINATION_REQUEST:',
            'extension': 'EXTENSION_REQUEST:'
        }
        prefix = prefix_map.get(instance.application_type)
        
        if not prefix:
            raise serializers.ValidationError("Rental applications cannot be edited via this endpoint.")
            
        # Find the existing note containing the JSON data
        note = instance.notes.filter(content__startswith=prefix).first()
        if not note:
            raise serializers.ValidationError("Application details not found.")
            
        try:
            json_str = note.content.replace(prefix, '')
            data = json.loads(json_str)
        except Exception:
            raise serializers.ValidationError("Failed to parse application details.")
            
        # UPDATE LOGIC BASED ON TYPE
        if instance.application_type == 'transfer':
            if 'to_unit_id' in validated_data:
                new_unit = Unit.objects.get(id=validated_data['to_unit_id'])
                # Allow keeping the same unit or changing to an available one
                if new_unit.status != 'available' and new_unit.id != data.get('to_unit'):
                    raise serializers.ValidationError({"to_unit_id": "Target unit is not available."})
                data['to_unit'] = new_unit.id
            if 'desired_move_in_date' in validated_data:
                data['desired_move_in_date'] = str(validated_data['desired_move_in_date'])
            if 'reason' in validated_data:
                data['reason'] = validated_data['reason']
            if 'notes' in validated_data:
                data['notes'] = validated_data['notes']
                
        elif instance.application_type == 'termination':
            if 'intended_vacate_date' in validated_data:
                data['date'] = str(validated_data['intended_vacate_date'])
            if 'reason' in validated_data:
                data['reason'] = validated_data['reason']
            if 'penalty_amount' in validated_data:
                data['penalty'] = str(validated_data['penalty_amount'])
                
        elif instance.application_type == 'extension':
            if 'new_end_date' in validated_data:
                data['new_end_date'] = str(validated_data['new_end_date'])
            if 'reason' in validated_data:
                data['reason'] = validated_data['reason']
                
        # SAVE UPDATED JSON BACK TO THE NOTE
        note.content = prefix + json.dumps(data)
        note.save(update_fields=['content'])
        
        return instance