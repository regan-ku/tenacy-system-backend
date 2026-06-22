from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from properties.models import Property, Location, Unit, UnitGroup
from .models import Application, RentalApplication, ApplicationDecision
from .services.application_service import ApplicationService
from .services.approval_service import ApprovalService

User = get_user_model()

class ApplicationsCoreRulesTests(TestCase):
    def setUp(self):
        # Create a landlord and a tenant
        self.landlord = User.objects.create_user(
            email='landlord@test.com', password='TestPass123!', role='landlord'
        )
        self.tenant = User.objects.create_user(
            email='tenant@test.com', password='TestPass123!', role='tenant'
        )
        self.agent = User.objects.create_user(
            email='agent@test.com', password='TestPass123!', role='agent'
        )
        
        # Create a property and location
        self.location = Location.objects.create(city='Nairobi', county='Nairobi', landmark='Test Landmark')
        self.property = Property.objects.create(
            title='Test Apartments', location=self.location, created_by=self.landlord,
            property_category='residential', property_sub_type='apartment', 
            number_of_floors=1, total_units_capacity=1, is_active=True, current_manager=self.landlord
        )
        
        # Create a unit
        self.unit = Unit.objects.create(
            property=self.property, unit_code='A-101', unit_type='one_bedroom',
            floor_number=1, rent_amount=15000, deposit_amount=15000, service_charge=0,
            billing_cycle='monthly', billing_date=5, status='available'
        )

    def test_max_30_applications_per_unit_rule(self):
        """Tests that a unit cannot exceed 30 active applications."""
        # Create 30 applications
        for i in range(30):
            user = User.objects.create_user(email=f'tenant{i}@test.com', password='TestPass123!', role='tenant')
            ApplicationService.create_rental_application(
                applicant=user, unit=self.unit, employment_status='employed', desired_move_in_date=timezone.now().date()
            )
            
        # The 31st application should fail
        with self.assertRaises(ValidationError) as context:
            ApplicationService.create_rental_application(
                applicant=self.tenant, unit=self.unit, employment_status='employed', desired_move_in_date=timezone.now().date()
            )
        self.assertIn("maximum limit of 30 active applications", str(context.exception))

    def test_agent_escalation_rule(self):
        """Tests that an agent cannot approve an application if conditions are not met."""
        # 1. Create an application
        app = ApplicationService.create_rental_application(
            applicant=self.tenant, unit=self.unit, employment_status='employed', desired_move_in_date=timezone.now().date()
        )
        
        # 2. Simulate a blocking flag (e.g., unit becomes unavailable)
        self.unit.status = 'occupied'
        self.unit.save()
        
        # 3. Agent attempts to approve
        with self.assertRaises(ValidationError) as context:
            ApprovalService.process_decision(
                application=app, decision='approved', reviewer=self.agent, reason='Looks good'
            )
        self.assertIn("Agent approval denied: Not all tenancy conditions are met", str(context.exception))
        
        # 4. Verify the application was NOT approved (it should remain pending or be rejected)
        app.refresh_from_db()
        self.assertNotEqual(app.status, Application.Status.APPROVED)