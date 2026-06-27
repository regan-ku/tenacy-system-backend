import json
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.applications.models.application import Application
from apps.applications.models.application_note import ApplicationNote
from apps.properties.models import Unit

User = get_user_model()

class ApplicationService:
    MAX_APPLICATIONS_PER_UNIT = 30

    @staticmethod
    @transaction.atomic
    def create_rental_application(applicant, unit: Unit, employment_status: str, desired_move_in_date) -> Application:
        existing_application = Application.objects.filter(applicant=applicant, unit=unit, status__in=['pending', 'under_review', 'approved', 'escalated']).exists()
        if existing_application: raise ValidationError("You have already applied for this unit.")
        if unit.status != 'available': raise ValidationError("Unit not available.")

        create_kwargs = {'applicant': applicant, 'property': unit.property_ref, 'unit': unit, 'status': 'pending'}
        if hasattr(Application, 'ApplicationType'): create_kwargs['application_type'] = Application.ApplicationType.RENTAL
        else: create_kwargs['application_type'] = 'rental'
            
        application = Application.objects.create(**create_kwargs)
        
        note_data = {"employment_status": employment_status, "desired_move_in_date": str(desired_move_in_date)}
        content = "RENTAL_REQUEST:" + json.dumps(note_data)
        ApplicationNote.objects.create(application=application, note_type='general', content=content, created_by=applicant)
        return application

    @staticmethod
    def create_transfer_application(applicant, current_tenancy, to_unit: Unit, reason: str, desired_move_in_date=None, notes='') -> Application:
        if to_unit.status != 'available': raise ValidationError("Target unit not available.")
        
        # ✅ FIXED: Block transfers at UNIT level (tenancy level), not tenant level
        # Only block if THIS specific unit (the one being transferred FROM) already has a pending transfer
        existing_transfer = Application.objects.filter(
            applicant=applicant,
            unit=current_tenancy.unit,  # ✅ Check by unit, not just applicant
            application_type='transfer',
            status__in=['pending', 'under_review', 'approved', 'escalated']
        ).exists()
        
        if existing_transfer: 
            raise ValidationError(f"A pending transfer already exists for unit {current_tenancy.unit.unit_code}. Please cancel or complete it first.")

        create_kwargs = {'applicant': applicant, 'property': current_tenancy.property, 'unit': current_tenancy.unit, 'status': 'pending'}
        if hasattr(Application, 'ApplicationType'): create_kwargs['application_type'] = Application.ApplicationType.TRANSFER
        else: create_kwargs['application_type'] = 'transfer'
            
        application = Application.objects.create(**create_kwargs)

        note_data = {
            "from_unit": current_tenancy.unit.id,
            "to_unit": to_unit.id,
            "reason": reason,
            "desired_move_in_date": str(desired_move_in_date) if desired_move_in_date else None,
            "notes": notes
        }
        content = "TRANSFER_REQUEST:" + json.dumps(note_data)
        ApplicationNote.objects.create(application=application, note_type='general', content=content, created_by=applicant)
        return application

    # ✅ NEW: Update transfer application (for editing pending transfers)
    @staticmethod
    @transaction.atomic
    def update_transfer_application(application, to_unit: Unit, reason: str, desired_move_in_date=None, notes=''):
        """
        Updates a pending transfer application.
        Only allowed if application is in pending/under_review status.
        """
        # Validate application can be edited
        if application.status not in ['pending', 'under_review']:
            raise ValidationError(f"Cannot edit application with status '{application.status}'. Only pending or under_review applications can be edited.")
        
        # Validate new target unit
        if to_unit.status != 'available' and to_unit != application.unit:
            # Allow same unit (no change) or available units
            raise ValidationError("Target unit is not available.")
        
        # Get current note to preserve from_unit
        note = application.notes.filter(content__startswith='TRANSFER_REQUEST:').first()
        if not note:
            raise ValidationError("Transfer details not found.")
        
        try:
            json_str = note.content.replace('TRANSFER_REQUEST:', '')
            old_data = json.loads(json_str)
            from_unit_id = old_data.get('from_unit')
        except Exception as e:
            raise ValidationError(f"Failed to parse transfer details: {str(e)}")
        
        # Update the note with new details
        new_note_data = {
            "from_unit": from_unit_id,  # Keep the same from_unit
            "to_unit": to_unit.id,      # Update to new target unit
            "reason": reason,
            "desired_move_in_date": str(desired_move_in_date) if desired_move_in_date else None,
            "notes": notes
        }
        
        new_content = "TRANSFER_REQUEST:" + json.dumps(new_note_data)
        note.content = new_content
        note.save(update_fields=['content'])
        
        return application

    @staticmethod
    def create_eviction_application(applicant, unit: Unit, notice_period_days: int, intended_vacate_date, reason_for_leaving: str, forwarding_address: str) -> Application:
        existing_termination = Application.objects.filter(applicant=applicant, unit=unit, application_type='termination', status__in=['pending', 'under_review', 'approved', 'escalated']).exists()
        if existing_termination: raise ValidationError("Pending termination already exists.")

        create_kwargs = {'applicant': applicant, 'property': unit.property_ref, 'unit': unit, 'status': 'pending'}
        if hasattr(Application, 'ApplicationType'): create_kwargs['application_type'] = Application.ApplicationType.TERMINATION
        else: create_kwargs['application_type'] = 'termination'
            
        application = Application.objects.create(**create_kwargs)

        note_data = {
            "date": str(intended_vacate_date) if intended_vacate_date else None,
            "penalty": 0,
            "reason": reason_for_leaving
        }
        content = "TERMINATION_REQUEST:" + json.dumps(note_data)
        ApplicationNote.objects.create(application=application, note_type='general', content=content, created_by=applicant)
        return application

    @staticmethod
    def create_extension_application(applicant, current_tenancy, new_end_date, reason='') -> Application:
        existing_extension = Application.objects.filter(
            applicant=applicant, 
            unit=current_tenancy.unit,
            application_type='extension', 
            status__in=['pending', 'under_review', 'approved', 'escalated']
        ).exists()
        if existing_extension: 
            raise ValidationError("Pending extension already exists.")

        if new_end_date <= timezone.now().date():
            raise ValidationError("New end date must be in the future.")

        create_kwargs = {
            'applicant': applicant, 
            'property': current_tenancy.property, 
            'unit': current_tenancy.unit, 
            'status': 'pending'
        }
        if hasattr(Application, 'ApplicationType'): 
            create_kwargs['application_type'] = Application.ApplicationType.EXTENSION
        else: 
            create_kwargs['application_type'] = 'extension'
            
        application = Application.objects.create(**create_kwargs)

        note_data = {
            "new_end_date": str(new_end_date) if new_end_date else None,
            "reason": reason
        }
        content = "EXTENSION_REQUEST:" + json.dumps(note_data)
        ApplicationNote.objects.create(
            application=application, 
            note_type='general', 
            content=content, 
            created_by=applicant
        )
        return application