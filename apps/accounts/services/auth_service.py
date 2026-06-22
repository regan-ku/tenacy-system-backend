from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class AuthService:
    """
    Handles all authentication-related business logic.
    """

    @staticmethod
    def login_user(email: str, password: str) -> dict:
        """
        Authenticates a user via email and password, returning JWT tokens.
        """
        # ✅ FIX: Strip whitespace and force lowercase to prevent case-sensitivity bugs
        email = email.strip().lower()
        password = password.strip()
        
        logger.info(f"🔐 Login attempt for email: {email}")
        
        # ✅ SMART AUTHENTICATION:
        # Django's authenticate() requires the keyword argument to match the model's USERNAME_FIELD.
        username_field = getattr(User, 'USERNAME_FIELD', 'username')
        
        if username_field == 'email':
            # If your Custom User model uses email as the primary login field
            user = authenticate(email=email, password=password)
        else:
            # If your model still uses 'username' as the primary field, 
            # we fetch the user by email first, then authenticate using their actual username.
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
        
        if user is None:
            logger.warning(f"❌ Authentication FAILED for email: {email}.")
            raise ValidationError("Invalid email or password.")
            
        if not user.is_active:
            logger.warning(f"⚠️ Account is INACTIVE for email: {email}")
            raise ValidationError("This account is currently inactive or suspended.")
            
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        logger.info(f"✅ Login SUCCESS for email: {email}, Role: {getattr(user, 'role', 'N/A')}")
        
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "role": getattr(user, 'role', 'tenant'),
                "phone_number": getattr(user, 'phone_number', ''),
                "is_verified": getattr(user, 'is_verified', False)
            }
        }