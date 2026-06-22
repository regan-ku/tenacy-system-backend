from django.db import models
from django.conf import settings

class DashboardSnapshot(models.Model):
    """
    Stores the exact aggregated state of a user's dashboard at a specific point in time.
    Enables historical comparisons, caching, and offline viewing without re-computing heavy aggregations.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard_snapshots',
        help_text="The user this dashboard snapshot belongs to."
    )

    role_at_time = models.CharField(
        'User Role at Time',
        max_length=20,
        help_text="The role the user had when this snapshot was taken."
    )

    # The actual aggregated KPI and widget data
    snapshot_data = models.JSONField(
        'Dashboard Data',
        help_text="The computed KPIs, chart data, and widget states at the time of capture."
    )

    captured_at = models.DateTimeField(
        'Captured At',
        auto_now_add=True,
        db_index=True,
        help_text="Exact timestamp when this dashboard state was frozen."
    )

    class Meta:
        verbose_name = 'Dashboard Snapshot'
        verbose_name_plural = 'Dashboard Snapshots'
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['user', 'captured_at']),
        ]

    def __str__(self):
        return f"Dashboard Snapshot for {self.user.email} at {self.captured_at.strftime('%Y-%m-%d %H:%M')}"