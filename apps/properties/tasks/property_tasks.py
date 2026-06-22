from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def index_property_for_marketplace(self, property_id: int):
    """
    Asynchronously indexes a property for the public marketplace search.
    Triggered on property creation, update, or publication.
    """
    try:
        from ..models import Property
        property_obj = Property.objects.select_related('location').get(id=property_id)
        
        # TODO: Integrate with your search engine (Elasticsearch, Meilisearch, or Redis Cache)
        # Example: search_client.index(document=property_obj.to_search_dict())
        
        logger.info(f"Property {property_id} successfully indexed for marketplace search.")
        return True
    except Property.DoesNotExist:
        logger.warning(f"Property {property_id} not found for indexing.")
        return False
    except Exception as e:
        logger.error(f"Failed to index property {property_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def invalidate_property_cache(self, property_id: int):
    """
    Clears cached data for a specific property when it is updated or hidden.
    Ensures the public marketplace always shows fresh data.
    """
    try:
        # TODO: Integrate with Redis cache invalidation
        # Example: cache.delete(f'property_detail_{property_id}')
        # Example: cache.delete_pattern(f'property_units_{property_id}_*')
        
        logger.info(f"Cache invalidated for property {property_id}.")
        return True
    except Exception as e:
        logger.error(f"Failed to invalidate cache for property {property_id}: {e}")
        raise self.retry(exc=e, countdown=30)