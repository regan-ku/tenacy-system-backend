from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

def get_tokens_for_user(user):
    """
    Generates fresh Access and Refresh tokens for a user.
    Ensures the token payload includes the user's role for frontend state resolution.
    """
    refresh = RefreshToken.for_user(user)
    
    # Inject custom claims into the token payload
    refresh['role'] = user.role
    refresh['email'] = user.email
    refresh['is_verified'] = user.is_verified

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def blacklist_refresh_token(token_string: str):
    """
    Blacklists a refresh token (e.g., on logout) to prevent reuse.
    """
    try:
        token = RefreshToken(token_string)
        token.blacklist()
        return True
    except Exception:
        return False