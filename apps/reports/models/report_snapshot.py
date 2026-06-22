from django.db import models

class ReportSnapshot(models.Model):
    """
    Stores the actual aggregated data payload at the exact time of report generation.
    Ensures historical reports remain immutable and consistent, even if 
    underlying operational data (e.g., a tenant's balance or unit status) is later modified.
    """
    report = models.OneToOneField(
        'Report',
        on_delete=models.CASCADE,
        related_name='snapshot',
        help_text="The parent report generation request this snapshot belongs to."
    )

    # The actual aggregated data (e.g., total revenue, occupancy %, chart data points, tabular rows)
    snapshot_data = models.JSONField(
        'Snapshot Data',
        help_text="The computed KPIs, charts, and tabular data at the time of generation."
    )

    taken_at = models.DateTimeField(
        'Snapshot Taken At',
        auto_now_add=True,
        help_text="Exact timestamp when this data was aggregated and locked."
    )

    class Meta:
        verbose_name = 'Report Data Snapshot'
        verbose_name_plural = 'Report Data Snapshots'
        ordering = ['-taken_at']

    def __str__(self):
        return f"Snapshot for {self.report.title} at {self.taken_at.strftime('%Y-%m-%d %H:%M')}"