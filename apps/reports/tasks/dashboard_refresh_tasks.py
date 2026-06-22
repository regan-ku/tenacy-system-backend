from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

from ..models import DashboardSnapshot
from ..services import DashboardService

User = get_user_model()
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def precompute_dashboard_snapshots(self, role: str = None):
    """
    Pre-computes dashboard data for active users and saves it as a DashboardSnapshot.
    This ensures that when the user logs in, their dashboard loads instantly from the cache.
    Recommended to run during off-peak hours (e.g., nightly) or every few hours.
    """
    try:
        # Filter users based on role, or target all active users if role is None
        users = User.objects.filter(is_active=True)
        if role:
            users = users.filter(role=role)

        cached_count = 0
        for user in users:
            try:
                # Fetch live dashboard data (this triggers the aggregators)
                dashboard_data = DashboardService.get_dashboard_data(user, role=user.role)
                
                # Save as a snapshot for historical comparison or instant loading
                DashboardSnapshot.objects.create(
                    user=user,
                    role_at_time=user.role,
                    snapshot_data=dashboard_data
                )
                cached_count += 1
            except Exception as user_error:
                # Log individual user failures but continue the batch
                logger.warning(f"Failed to precompute dashboard for user {user.id}: {str(user_error)}")
                continue

        logger.info(f"Pre-computed {cached_count} dashboard snapshots for role: {role or 'all'}.")
        return {"cached": cached_count}
    except Exception as e:
        logger.error(f"Failed to precompute dashboard snapshots: {str(e)}")
        raise self.retry(exc=e, countdown=600)