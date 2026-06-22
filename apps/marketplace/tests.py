from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ..models import PropertyPublication, Listing, UnitGroupAvailability
from ..services.availability_service import AvailabilityService
from ..services.publishing_service import PublishingService
from properties.models import Property, Location, UnitGroup

User = get_user_model()

class MarketplaceServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@test.com', password='TestPass123!')
        self.location = Location.objects.create(city='Nairobi', county='Nairobi', landmark='Test Landmark')
        self.property = Property.objects.create(
            title='Test Apartments', location=self.location, created_by=self.user,
            property_category='residential', property_sub_type='apartment', 
            allows_pets=True, parking_spaces=2, is_active=True
        )
        self.unit_group = UnitGroup.objects.create(
            property=self.property, name='Block A', unit_type='one_bedroom',
            floor_range='1', billing_cycle='monthly', billing_date=5, base_rent_amount=15000, capacity=2
        )

    def test_availability_auto_hide_rule(self):
        """Tests that unit groups auto-hide from marketplace when available_units hits 0."""
        avail = UnitGroupAvailability.objects.create(
            unit_group=self.unit_group, total_units=2, available_units=2
        )
        self.assertTrue(avail.is_marketplace_visible)
        
        # Simulate occupancy
        avail.available_units = 1
        avail.save()
        self.assertTrue(avail.is_marketplace_visible)
        
        # Simulate full occupancy
        avail.available_units = 0
        avail.save()
        self.assertFalse(avail.is_marketplace_visible) # MUST auto-hide

    def test_publishing_validation_requires_location_and_media(self):
        """Tests that a property cannot be published without a location or media."""
        # Create publication record first
        PropertyPublication.objects.create(property=self.property)
        
        # Attempt to publish should fail due to missing cover_photo/media
        with self.assertRaises(ValidationError):
            PublishingService.publish_property(self.property, self.user)

    def test_get_availability_summary(self):
        """Tests that the availability service returns correctly formatted frontend data."""
        UnitGroupAvailability.objects.create(
            unit_group=self.unit_group, total_units=3, available_units=1
        )
        summary = AvailabilityService.get_availability_summary(self.unit_group)
        
        self.assertEqual(summary['available_units'], 1)
        self.assertEqual(summary['availability_text'], "1 unit remaining")
        self.assertTrue(summary['is_visible'])