import re
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

def validate_phone_number(value):
    """
    Validates phone numbers. 
    Accepts: Kenyan format (+254712345678, 0712345678, 0112345678) 
    OR any valid international E.164 format (+1234567890).
    """
    kenya_pattern = r'^(?:\+254|0)(?:7\d{8}|1\d{8})$'
    e164_pattern = r'^\+[1-9]\d{1,14}$'
    
    if not re.match(kenya_pattern, value) and not re.match(e164_pattern, value):
        raise ValidationError(
            'Enter a valid phone number (e.g., +254712345678, 0712345678, or +1234567890).'
        )

def validate_kra_pin(value):
    """
    Validates Kenyan KRA PIN format: 1 Letter, 9 Digits, 1 Letter (e.g., A012345678B).
    """
    kra_pattern = r'^[a-zA-Z]{1}[0-9]{9}[a-zA-Z]{1}$'
    if not re.match(kra_pattern, str(value).upper()):
        raise ValidationError('Enter a valid KRA PIN (e.g., A012345678B).')
    return str(value).upper()

def validate_national_id(value):
    """
    Validates Kenyan National ID (7 to 8 digits).
    """
    id_pattern = r'^\d{7,8}$'
    if not re.match(id_pattern, str(value)):
        raise ValidationError('Enter a valid National ID number (7 or 8 digits).')

class CustomPasswordValidator:
    """
    Ensures passwords meet enterprise security standards.
    """
    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one digit.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')

    def get_help_text(self):
        return (
            "Your password must be at least 8 characters long, and contain "
            "at least one uppercase letter, one lowercase letter, one digit, "
            "and one special character."
        )

def validate_strict_email(value):
    """
    Standard email validation, plus blocking of known disposable email domains.
    """
    email_validator = EmailValidator(message="Enter a valid email address.")
    email_validator(value)
    
    disposable_domains = ['tempmail.com', 'throwaway.com', 'mailinator.com', 'guerrillamail.com', '10minutemail.com']
    domain = str(value).split('@')[1].lower()
    if domain in disposable_domains:
        raise ValidationError('Disposable email addresses are not allowed for security reasons.')