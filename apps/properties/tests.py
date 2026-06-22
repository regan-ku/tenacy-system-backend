from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Property, Location, UnitGroup, Unit
from properties.models.enums import PropertyCategory, PropertySubType, UnitType, BillingCycle

User = get_user_model()

class PropertiesModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='landlord@test.com', phone='+254712345678', password='TestPass123!', role='landlord'
        )
        self.location = Location.objects.create(city='Nairobi', county='Nairobi', landmark='Opposite Westlands Mall')
        self.property = Property.objects.create(
            title='Sunrise Apartments',
            property_category=PropertyCategory.RESIDENTIAL,
            property_sub_type=PropertySubType.APARTMENT,
            location=self.location,
            created_by=self.user,
            number_of_floors=3,
            total_units_capacity=10,
            allows_pets=True,
            parking_spaces=15
        )

    def test_property_creation(self):
        self.assertEqual(self.property.title, 'Sunrise Apartments')
        self.assertTrue(self.property.is_active)
        self.assertFalse(self.property.is_single_unit_property)

    def test_unit_group_creation(self):
        unit_group = UnitGroup.objects.create(
            property=self.property, name='Block A', unit_type=UnitType.TWO_BEDROOM,
            floor_range='1-3', billing_cycle=BillingCycle.MONTHLY, billing_date=5,
            base_rent_amount=15000.00, capacity=6
        )
        self.assertEqual(unit_group.base_rent_amount, 15000.00)
        self.assertEqual(unit_group.currency, 'KES')

    def test_unit_inheritance_logic(self):
        unit_group = UnitGroup.objects.create(
            property=self.property, name='Block B', unit_type=UnitType.ONE_BEDROOM,
            floor_range='1', billing_cycle=BillingCycle.MONTHLY, billing_date=5,
            base_rent_amount=10000.00, capacity=1
        )
        unit = Unit.objects.create(
            property=self.property, unit_group=unit_group, unit_code='B-101',
            unit_type=UnitType.ONE_BEDROOM, floor_number=1, rent_amount=10000.00,
            billing_cycle=BillingCycle.MONTHLY, billing_date=5, status='available'
        )
        # Verify @property inheritance methods work correctly
        self.assertTrue(unit.allows_pets)  # Inherited from property
        self.assertEqual(unit.parking_spaces, 15)  # Inherited from property
        self.assertEqual(unit.currency, 'KES')  # Hardcoded/Property default