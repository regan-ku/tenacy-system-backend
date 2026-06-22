from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

class AccountsModelTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            'email': 'test@example.com',
            'phone': '+254712345678',
            'password': 'SecurePass123!',
            'role': User.Role.TENANT
        }

    def test_user_creation(self):
        """Test that a user can be created with the custom model."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_verified)

    def test_str_method(self):
        """Test the string representation of the user."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(str(user), 'test@example.com (Tenant)')