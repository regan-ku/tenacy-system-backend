from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Application
from apps.tenancy.services.tenancy_service import TenancyService
from apps.tenancy.services.transfer_service import TransferService

class TenancyIntegrationService:
    """
    Bridges the Applications app with the Tenancy app.
    Executes the actual tenancy creation or transfer once an application is approved.
    """

    @staticmethod
    @transaction.atomic
    def execute_approved_application(application: Application):
        app_type = getattr(application, 'application_type', None)
        
        if app_type in ['rental', getattr(Application.ApplicationType, 'RENTAL', None)]:
            TenancyIntegrationService._create_new_tenancy(application)
        elif app_type in ['transfer', getattr(Application.ApplicationType, 'TRANSFER', None)]:
            TenancyIntegrationService._execute_transfer(application)
        else:
            raise ValidationError("Invalid application type for tenancy integration.")

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
            tenant=application.applicant,
            unit=unit,
            property_obj=property_obj,
            created_by=application.applicant, 
            rent_amount=rent_amount,
            deposit_amount=deposit_amount,
            service_charge_amount=service_charge,
            tenancy_type='rental',
            start_date=start_date,
            end_date=None 
        )
        
        # ✅ CRITICAL: Explicitly set status to 'pending_payment'
        # This allows the 3-hour recall task to identify unpaid tenancies.
        tenancy.status = 'pending_payment'
        tenancy.save(update_fields=['status'])
        
        return tenancy

    @staticmethod
    def _execute_transfer(application: Application):
        transfer_details = getattr(application, 'transfer_details', None) or getattr(application, 'transfer_application', None)
        
        if not transfer_details:
            raise ValidationError("Transfer details are missing from the approved application.")

        class MockTransferRequest:
            def __init__(self, details, app):
                self.tenant = app.applicant
                self.from_property = getattr(details, 'from_property', None)
                self.from_unit = getattr(details, 'from_unit', None)
                self.to_property = getattr(details, 'to_property', None)
                self.to_unit = getattr(details, 'to_unit', None)
                self.reason = getattr(details, 'reason', '')
                self.transfer_status = 'pending'
                self.approved_by = None
                self.processed_at = None

        mock_request = MockTransferRequest(transfer_details, application)
        
        new_tenancy = TransferService.execute_transfer(
            transfer_request=mock_request,
            approved_by=application.applicant 
        )
        
        return new_tenancy