from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from properties.models import Property, Location, Unit, UnitGroup
from .models import Tenancy, Occupancy
from .services.tenancy_service import TenancyService
from .services.validation_service import TenancyValidationService

User = get_user_model()

class TenancyCoreRulesTests(TestCase):
    def setUp(self):
        # Create a landlord user
        self.landlord = User.objects.create_user(
            email='landlord@test.com', password='TestPass123!', role='landlord'
        )
        
        # Create a property and location
        self.location = Location.objects.create(city='Nairobi', county='Nairobi', landmark='Test Landmark')
        self.property = Property.objects.create(
            title='Test Apartments', location=self.location, created_by=self.landlord,
            property_category='residential', property_sub_type='apartment', 
            number_of_floors=2, total_units_capacity=2, is_active=True
        )
        
        # Create a unit group and a unit
        self.unit_group = UnitGroup.objects.create(
            property=self.property, name='Block A', unit_type='one_bedroom',
            floor_range='1', billing_cycle='monthly', billing_date=5, base_rent_amount=15000, capacity=2
        )
        self.unit = Unit.objects.create(
            property=self.property, unit_group=self.unit_group, unit_code='A-101',
            unit_type='one_bedroom', floor_number=1, rent_amount=15000,
            billing_cycle='monthly', billing_date=5, status='available'
        )
        
        # Create a tenant user
        self.tenant = User.objects.create_user(
            email='tenant@test.com', password='TestPass123!', role='tenant'
        )

    def test_unit_availability_validation(self):
        """Tests that an occupied unit cannot be assigned a new tenancy."""
        # 1. Create and activate first tenancy
        tenancy1 = TenancyService.create_tenancy(
            tenant=self.tenant, unit=self.unit, property_obj=self.property,
            created_by=self.landlord, rent_amount=15000, deposit_amount=15000, service_charge_amount=0
        )
        tenancy1.deposit_paid = True
        tenancy1.service_charge_paid = True
        tenancy1.save()
        TenancyService.activate_tenancy(tenancy1, activated_by=self.landlord)

        # 2. Attempt to create a second tenancy for the SAME unit should fail validation
        tenant2 = User.objects.create_user(email='tenant2@test.com', password='TestPass123!', role='tenant')
        
        with self.assertRaises(ValidationError):
            TenancyValidationService.validate_unit_availability(self.unit)

    def test_activation_financial_gate(self):
        """Tests that a tenancy cannot be activated unless deposit/service charge is paid or waived."""
        tenancy = TenancyService.create_tenancy(
            tenant=self.tenant, unit=self.unit, property_obj=self.property,
            created_by=self.landlord, rent_amount=15000, deposit_amount=15000, service_charge_amount=5000
        )
        
        # Should fail because nothing is paid or waived
        with self.assertRaises(ValidationError):
            TenancyService.activate_tenancy(tenancy, activated_by=self.landlord)
            
        # Waive the fees
        tenancy.deposit_waived = True
        tenancy.service_charge_waived = True
        tenancy.save()
        
        # Should now succeed
        activated_tenancy = TenancyService.activate_tenancy(tenancy, activated_by=self.landlord)
        self.assertEqual(activated_tenancy.status, 'active')
        
        # Verify occupancy was updated
        self.assertTrue(self.unit.occupancy_record.is_occupied)
        self.assertEqual(self.unit.status, 'occupied')