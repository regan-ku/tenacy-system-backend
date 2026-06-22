from django.db import models
from django.conf import settings

class MoveInOutRecord(models.Model):
    """
    Tracks physical move-in and move-out events, including condition reports 
    and key handovers to ensure accountability.
    """
    class EventType(models.TextChoices):
        MOVE_IN = 'move_in', 'Move In'
        MOVE_OUT = 'move_out', 'Move Out'

    tenancy = models.ForeignKey(
        'Tenancy',
        on_delete=models.CASCADE,
        related_name='move_records',
        help_text="The tenancy associated with this move event."
    )

    event_type = models.CharField(
        'Event Type',
        max_length=20,
        choices=EventType.choices
    )

    scheduled_date = models.DateField('Scheduled Date')
    actual_date = models.DateField('Actual Date', blank=True, null=True)

    condition_report_notes = models.TextField(
        'Condition Report Notes', 
        blank=True, 
        null=True,
        help_text="Notes on the state of the unit (e.g., existing damages, cleanliness)."
    )

    keys_handed_over = models.BooleanField('Keys Handed Over', default=False)
    utilities_transferred = models.BooleanField('Utilities Transferred/Activated', default=False)

    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='conducted_move_records',
        help_text="Manager or agent who conducted the move-in/out inspection."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Move In/Out Record'
        verbose_name_plural = 'Move In/Out Records'
        ordering = ['-scheduled_date']
        indexes = [
            models.Index(fields=['tenancy', 'event_type']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} for {self.tenancy.unit.unit_code} on {self.scheduled_date}"