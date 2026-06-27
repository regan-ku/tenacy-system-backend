import json # ✅ CRITICAL: Import JSON to match the application_service
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
from ..models import Application
from apps.tenancy.models import Tenancy
from apps.tenancy.services.tenancy_service import TenancyService

class TenancyIntegrationService:
    @staticmethod
    @transaction.atomic
    def execute_approved_application(application: Application):
        app_type = getattr(application, 'application_type', None)
        is_rental = app_type in ['rental', getattr(Application.ApplicationType, 'RENTAL', None)]
        is_transfer = app_type in ['transfer', getattr(Application.ApplicationType, 'TRANSFER', None)]
        is_termination = app_type in ['termination', getattr(Application.ApplicationType, 'TERMINATION', None)]
        is_extension = app_type in ['extension', getattr(Application.ApplicationType, 'EXTENSION', None)]

        if is_rental: return TenancyIntegrationService._create_new_tenancy(application)
        elif is_transfer: return TenancyIntegrationService._execute_transfer_as_pending(application)
        elif is_termination: return TenancyIntegrationService._execute_termination_approval(application)
        elif is_extension: return TenancyIntegrationService._execute_extension_approval(application)
        else: raise ValidationError("Invalid application type.")

    @staticmethod
    def _create_new_tenancy(application: Application):
        rental_details = getattr(application, 'rental_details', None) or getattr(application, 'rental_application', None)
        unit = application.unit
        property_obj = getattr(application, 'property_ref', None) or getattr(application, 'property', None)
        rent_amount = getattr(unit, 'rent_amount', None) or getattr(unit, 'base_rent_amount', 0)
        deposit_amount = getattr(unit, 'deposit_amount', 0)
        service_charge = getattr(unit, 'service_charge', None) or getattr(unit, 'service_charge_amount', 0)
        start_date = getattr(rental_details, 'desired_move_in_date', None) if rental_details else None

        tenancy = TenancyService.create_tenancy(
            tenant=application.applicant, unit=unit, property_obj=property_obj,
            created_by=application.applicant, rent_amount=rent_amount, deposit_amount=deposit_amount,
            service_charge_amount=service_charge, tenancy_type='rental', start_date=start_date, end_date=None 
        )
        tenancy.status = 'pending_payment'
        tenancy.save(update_fields=['status'])
        return tenancy

    @staticmethod
    def _execute_transfer_as_pending(application: Application):
        transfer_details = getattr(application, 'transfer_details', None) or getattr(application, 'transfer_application', None)
        
        if not transfer_details:
            from apps.applications.models import ApplicationNote
            from apps.properties.models import Unit
            
            note = application.notes.filter(content__startswith='TRANSFER_REQUEST:').first()
            if note:
                try:
                    json_str = note.content.replace('TRANSFER_REQUEST:', '')
                    data = json.loads(json_str) # ✅ Parse as JSON
                    
                    class MockDetails:
                        def __init__(self, d):
                            self.to_unit = Unit.objects.get(id=d['to_unit'])
                            self.from_unit = Unit.objects.get(id=d['from_unit'])
                            self.reason = d.get('reason', '')
                            
                            # ✅ DATE SAFEGUARD
                            date_str = d.get('desired_move_in_date')
                            if date_str:
                                parsed_date = parse_date(str(date_str))
                                if parsed_date and parsed_date >= timezone.now().date():
                                    self.desired_move_in_date = parsed_date
                                else:
                                    self.desired_move_in_date = timezone.now().date() # Fallback to today if past
                            else:
                                self.desired_move_in_date = timezone.now().date()
                                
                            self.notes = d.get('notes', '')
                            
                    transfer_details = MockDetails(data)
                except Exception as e:
                    print(f"Error parsing transfer note: {e}")

        if not transfer_details:
            raise ValidationError("Transfer details are missing from the approved application.")

        to_unit = getattr(transfer_details, 'to_unit', None)
        from_unit = getattr(transfer_details, 'from_unit', None)
        if not to_unit: raise ValidationError("Target unit missing.")

        from_tenancy = Tenancy.objects.filter(unit=from_unit, tenant=application.applicant, status__in=['active', 'extended']).first()
        if not from_tenancy: raise ValidationError("No active tenancy found to transfer from.")

        rent_amount = getattr(to_unit, 'rent_amount', 0) or getattr(to_unit, 'base_rent_amount', 0)
        deposit_amount = getattr(to_unit, 'deposit_amount', 0)
        service_charge = getattr(to_unit, 'service_charge', 0) or getattr(to_unit, 'service_charge_amount', 0)
        
        move_in_date = getattr(transfer_details, 'desired_move_in_date', None) or timezone.now().date()

        new_tenancy = TenancyService.create_tenancy(
            tenant=application.applicant, unit=to_unit, property_obj=to_unit.property,
            created_by=application.applicant, rent_amount=rent_amount, deposit_amount=deposit_amount,
            service_charge_amount=service_charge, tenancy_type='transfer', start_date=move_in_date, end_date=None
        )
        
        new_tenancy.status = 'pending_payment'
        new_tenancy.deposit_paid = False
        new_tenancy.deposit_waived = False
        new_tenancy.service_charge_paid = False
        new_tenancy.service_charge_waived = False
        new_tenancy.save()
            
        return new_tenancy

    @staticmethod
    def _execute_termination_approval(application: Application):
        termination_details = getattr(application, 'termination_details', None) or getattr(application, 'termination_application', None)
        
        if not termination_details:
            from apps.applications.models import ApplicationNote
            note = application.notes.filter(content__startswith='TERMINATION_REQUEST:').first()
            if note:
                try:
                    json_str = note.content.replace('TERMINATION_REQUEST:', '')
                    data = json.loads(json_str) # ✅ Parse as JSON
                    
                    class MockDetails:
                        def __init__(self, d):
                            # ✅ DATE SAFEGUARD
                            date_str = d.get('date')
                            if date_str:
                                parsed_date = parse_date(str(date_str))
                                if parsed_date and parsed_date >= timezone.now().date():
                                    self.proposed_move_out_date = parsed_date
                                else:
                                    self.proposed_move_out_date = timezone.now().date() # Fallback to today if past
                            else:
                                self.proposed_move_out_date = timezone.now().date()
                                
                            self.penalty_amount = float(d.get('penalty', 0))
                            self.notes = d.get('reason', '')
                            
                    termination_details = MockDetails(data)
                except Exception as e:
                    print(f"Error parsing termination note: {e}")

        if not termination_details: raise ValidationError("Termination details missing.")

        tenancy = Tenancy.objects.filter(tenant=application.applicant, status__in=['active', 'extended']).first()
        if not tenancy: raise ValidationError("No active tenancy found.")

        move_out_date = getattr(termination_details, 'proposed_move_out_date', None) or timezone.now().date()
        penalty_amount = getattr(termination_details, 'penalty_amount', 0) or 0
        
        if penalty_amount > 0:
            try:
                from apps.payments.services.invoice_service import InvoiceService
                InvoiceService.create_penalty_invoice(tenancy=tenancy, amount=penalty_amount, reason=f"Termination penalty: {getattr(termination_details, 'notes', '')}")
            except Exception as e: print(f"⚠️ Failed to create penalty invoice: {e}")

        tenancy.end_date = move_out_date
        if hasattr(Tenancy.Status, 'SCHEDULED_FOR_TERMINATION'): tenancy.status = Tenancy.Status.SCHEDULED_FOR_TERMINATION
        else: tenancy.status = 'scheduled_for_termination'
        tenancy.save(update_fields=['end_date', 'status'])
        return tenancy

    # ✅ UPDATED: EXTENSION LOGIC WITH JSON PARSING & DATE SAFEGUARD
    @staticmethod
    def _execute_extension_approval(application: Application):
        """EXTENSION LOGIC: Updates the tenancy end date."""
        extension_details = getattr(application, 'extension_details', None) or getattr(application, 'extension_application', None)
        
        # ✅ FALLBACK: Parse from ApplicationNote JSON
        if not extension_details:
            from apps.applications.models import ApplicationNote
            note = application.notes.filter(content__startswith='EXTENSION_REQUEST:').first()
            if note:
                try:
                    json_str = note.content.replace('EXTENSION_REQUEST:', '')
                    data = json.loads(json_str) # ✅ Parse as JSON
                    
                    class MockDetails:
                        def __init__(self, d):
                            date_str = d.get('new_end_date')
                            if date_str:
                                parsed_date = parse_date(str(date_str))
                                if parsed_date and parsed_date >= timezone.now().date():
                                    self.new_end_date = parsed_date
                                else:
                                    # Fallback to 30 days from today if past/invalid
                                    self.new_end_date = timezone.now().date() + timedelta(days=30)
                            else:
                                self.new_end_date = timezone.now().date() + timedelta(days=30)
                            self.reason = d.get('reason', '')
                            
                    extension_details = MockDetails(data)
                except Exception as e:
                    print(f"Error parsing extension note: {e}")
        
        if not extension_details: 
            raise ValidationError("Extension details missing.")
        
        tenancy = Tenancy.objects.filter(
            tenant=application.applicant, 
            status__in=['active', 'extended']
        ).first()
        if not tenancy: 
            raise ValidationError("No active tenancy found.")
        
        new_end_date = getattr(extension_details, 'new_end_date', None) or getattr(extension_details, 'requested_new_end_date', None)
        if not new_end_date: 
            raise ValidationError("New end date missing.")
        
        tenancy.end_date = new_end_date
        if hasattr(Tenancy.Status, 'EXTENDED'): 
            tenancy.status = Tenancy.Status.EXTENDED
        else: 
            tenancy.status = 'extended'
        tenancy.save(update_fields=['end_date', 'status'])
        return tenancy