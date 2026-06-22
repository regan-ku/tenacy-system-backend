from django.db import models

class UserRole(models.TextChoices):
    """
    Centralized definition of all system roles.
    Used across User model, Permissions, and Dashboard routing.
    """
    ADMIN = 'admin', 'System Administrator'
    LANDLORD = 'landlord', 'Landlord / Property Owner'
    AGENCY = 'agency', 'Real Estate Agency'
    AGENT = 'agent', 'Agency Agent'
    CARETAKER = 'caretaker', 'Property Caretaker'
    TENANT = 'tenant', 'Tenant'

# Helper function to get role display names cleanly
def get_role_display_name(role_value: str) -> str:
    return dict(UserRole.choices).get(role_value, 'Unknown Role')