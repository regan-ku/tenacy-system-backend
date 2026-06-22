from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.exceptions import ValidationError

from .models import Agency, AgencyDirector, AgencyVerification, DelegatedProperty
from .services import AgencyService, DirectorService, AgencyVerificationService

User = get_user_model()

class AgenciesModelTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email='admin@tennacy.com',
            phone='+254712345678',
            password='SecurePass123!',
            role=User.Role.ADMIN
        )
        self.landlord_user = User.objects.create_user(
            email='landlord@tennacy.com',
            phone='+254722345678',
            password='SecurePass123!',
            role=User.Role.LANDLORD,
            is_verified=True
        )
        self.agency_user = User.objects.create_user(
            email='agency@tennacy.com',
            phone='+254732345678',
            password='SecurePass123!',
            role=User.Role.AGENCY
        )

    def test_agency_creation(self):
        """Test that an agency can be created and starts in pending verification."""
        agency = AgencyService.create_agency(
            created_by_user=self.agency_user,
            name="Sunrise Properties Ltd",
            registration_number="PVT-XY12345",
            contact_email="info@sunrise.com",
            phone_number="+254712345678",
            physical_address="Nairobi, Kenya"
        )
        self.assertEqual(agency.name, "Sunrise Properties Ltd")
        self.assertEqual(agency.status, Agency.Status.PENDING_VERIFICATION)
        self.assertFalse(agency.is_active)
        self.assertTrue(hasattr(agency, 'verification_record'))

    def test_director_requires_id_or_passport(self):
        """Test that a director cannot be created without an ID or Passport."""
        agency = Agency.objects.create(
            name="Test Agency",
            registration_number="PVT-TEST",
            contact_email="test@test.com",
            phone_number="+254712345678",
            physical_address="Nairobi"
        )
        with self.assertRaises(ValidationError):
            DirectorService.add_director(
                agency=agency,
                created_by_user=self.admin_user,
                full_name="John Doe",
                national_id=None,
                passport_number=None, # Both null should fail
                email="john@test.com",
                phone_number="+254712345678",
                nationality="Kenyan",
                address="Nairobi"
            )

    def test_agency_activation_requires_verified_director(self):
        """Test that an agency cannot be activated without at least one verified director."""
        agency = AgencyService.create_agency(
            created_by_user=self.agency_user,
            name="Activation Test Agency",
            registration_number="PVT-ACT123",
            contact_email="act@test.com",
            phone_number="+254712345678",
            physical_address="Nairobi"
        )
        
        # Add an unverified director
        DirectorService.add_director(
            agency=agency,
            created_by_user=self.admin_user,
            full_name="Jane Doe",
            national_id="12345678",
            email="jane@test.com",
            phone_number="+254712345678",
            nationality="Kenyan",
            address="Nairobi"
        )

        # Attempt to activate should fail
        with self.assertRaises(ValidationError):
            AgencyService.activate_agency(agency, self.admin_user)

    def test_successful_agency_activation(self):
        """Test that an agency activates successfully when both business and director are verified."""
        agency = AgencyService.create_agency(
            created_by_user=self.agency_user,
            name="Fully Verified Agency",
            registration_number="PVT-FULL123",
            contact_email="full@test.com",
            phone_number="+254712345678",
            physical_address="Nairobi"
        )
        
        # 1. Verify Director
        director = DirectorService.add_director(
            agency=agency,
            created_by_user=self.admin_user,
            full_name="Mark Smith",
            national_id="87654321",
            email="mark@test.com",
            phone_number="+254712345678",
            nationality="Kenyan",
            address="Nairobi"
        )
        DirectorService.verify_director(director, self.admin_user, 'verified')

        # 2. Verify Business
        verification = agency.verification_record
        AgencyVerificationService.review_business_verification(verification, self.admin_user, 'verified')

        # 3. Check Agency Status
        agency.refresh_from_db()
        self.assertEqual(agency.status, Agency.Status.ACTIVE)
        self.assertTrue(agency.is_active)