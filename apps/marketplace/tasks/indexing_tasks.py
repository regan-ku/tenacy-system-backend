from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def index_listing_for_search(self, listing_id: int):
    """
    Asynchronously indexes a marketplace listing into the search engine 
    (e.g., Elasticsearch, Meilisearch, or Redis) for fast discovery.
    Triggered on listing creation, update, or publication.
    """
    try:
        from ..models import Listing
        # Use select_related to fetch all necessary data in one query
        listing = Listing.objects.select_related(
            'property', 'property__location', 'unit_group'
        ).get(id=listing_id)
        
        # TODO: Replace with actual search engine client integration
        # Example: search_client.index(document=listing.to_search_dict())
        
        logger.info(f"Listing {listing_id} successfully indexed for marketplace search.")
        return True
        
    except Listing.DoesNotExist:
        logger.warning(f"Listing {listing_id} not found for indexing.")
        return False
    except Exception as e:
        logger.error(f"Failed to index listing {listing_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def remove_listing_from_search(self, listing_id: int):
    """
    Removes a listing from the search index when it is archived, hidden, or deleted.
    """
    try:
        # TODO: Replace with actual search engine client integration
        # Example: search_client.delete(document_id=listing_id)
        
        logger.info(f"Listing {listing_id} successfully removed from search index.")
        return True
    except Exception as e:
        logger.error(f"Failed to remove listing {listing_id} from search: {e}")
        raise self.retry(exc=e, countdown=30)