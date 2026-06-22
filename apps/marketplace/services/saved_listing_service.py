from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import SavedListing, Listing

class SavedListingService:
    """
    Manages user bookmarks, watchlists, and favorite properties for retargeting and engagement.
    """

    @staticmethod
    @transaction.atomic
    def save_listing(user, listing: Listing, notes: str = "") -> SavedListing:
        """
        Saves a listing to a user's watchlist.
        """
        if listing.status != 'active':
            raise ValidationError("Cannot save an inactive or unavailable listing.")

        saved, created = SavedListing.objects.get_or_create(
            user=user,
            listing=listing,
            defaults={'notes': notes}
        )
        
        if not created and notes:
            saved.notes = notes
            saved.save(update_fields=['notes'])
            
        return saved

    @staticmethod
    @transaction.atomic
    def unsave_listing(user, listing_id: int) -> bool:
        """
        Removes a listing from a user's watchlist.
        """
        deleted_count, _ = SavedListing.objects.filter(user=user, listing_id=listing_id).delete()
        return deleted_count > 0

    @staticmethod
    def get_user_saved_listings(user, limit: int = 50):
        """
        Retrieves a user's saved listings, ordered by most recently saved.
        Automatically filters out listings that are no longer active/visible.
        """
        return SavedListing.objects.filter(
            user=user,
            listing__status='active',
            listing__property__is_active=True,
            listing__property__publication__is_published=True,
            listing__property__publication__visibility_status='visible'
        ).select_related(
            'listing', 'listing__property', 'listing__property__location'
        ).order_by('-created_at')[:limit]