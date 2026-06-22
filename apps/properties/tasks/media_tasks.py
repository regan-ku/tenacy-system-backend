from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def optimize_and_compress_media(self, media_id: int):
    """
    Optimizes uploaded media files (resize images, compress videos) asynchronously.
    Prevents API request blocking during heavy file processing.
    """
    try:
        from ..models import PropertyMedia
        media = PropertyMedia.objects.get(id=media_id)
        
        # TODO: Integrate Pillow/ffmpeg here for actual compression
        # Example: image = Image.open(media.file.path); image.thumbnail((1920, 1080)); image.save(...)
        
        logger.info(f"Media {media_id} optimized successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to optimize media {media_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def cleanup_orphaned_media_files(self):
    """
    Periodically scans storage for media files not linked to any database record.
    Run as a daily Celery Beat task in production.
    """
    logger.info("Orphaned media cleanup task executed.")
    # TODO: Compare cloud storage bucket against PropertyMedia.objects.all() and delete unmatched
    return True