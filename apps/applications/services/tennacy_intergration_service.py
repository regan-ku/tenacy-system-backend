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
        """
        Routes the approved application to the correct tenancy execution service.
        """
        if application.application_type == Application.ApplicationType.RENTAL:
            TenancyIntegrationService._create_new_tenancy(application)
        elif application.application_type == Application.ApplicationType.TRANSFER:
            TenancyIntegrationService._execute_transfer(application)
        else:
            raise ValidationError("Invalid application type for tenancy integration.")

    @staticmethod
    def _create_new_tenancy(application: Application):
        """
        Creates a new tenancy record for an approved rental application.
        """
        rental_details = application.rental_details
        unit = application.unit
        
        # Create tenancy in 'pending_payment' status
        # The tenant will still need to pay/waive deposit and service charge to activate it
        tenancy = TenancyService.create_tenancy(
            tenant=application.applicant,
            unit=unit,
            property_obj=application.property,
            created_by=application.applicant, # Or the approving manager
            rent_amount=unit.rent_amount,
            deposit_amount=unit.deposit_amount,
            service_charge_amount=unit.service_charge,
            tenancy_type='rental',
            start_date=rental_details.desired_move_in_date,
            end_date=None # Will be set by lease agreement later
        )
        
        return tenancy

    @staticmethod
    def _execute_transfer(application: Application):
        """
        Executes a tenant transfer for an approved transfer application.
        """
        transfer_details = application.transfer_details
        
        # We mock a transfer request object to pass to the TransferService
        # In a real scenario, you might want to create a TenancyTransfer model instance 
        # during the application phase and link it here.
        class MockTransferRequest:
            def __init__(self, details, app):
                self.tenant = app.applicant
                self.from_property = details.from_property
                self.from_unit = details.from_unit
                self.to_property = details.to_property
                self.to_unit = details.to_unit
                self.reason = details.reason
                self.transfer_status = 'pending'
                self.approved_by = None
                self.processed_at = None

        mock_request = MockTransferRequest(transfer_details, application)
        
        # Execute the transfer (this handles releasing the old unit and occupying the new one)
        new_tenancy = TransferService.execute_transfer(
            transfer_request=mock_request,
            approved_by=application.applicant # Or the approving manager
        )
        
        return new_tenancy