from django.db import models
from django.conf import settings

class TenancyNote(models.Model):
    """
    Internal, append-only communication and audit log for a specific tenancy.
    Used for manager notes, dispute records, and handover instructions.
    """
    class NoteType(models.TextChoices):
        GENERAL = 'general', 'General Note'
        DISPUTE = 'dispute', 'Dispute Record'
        MAINTENANCE = 'maintenance', 'Maintenance Issue'
        HANDOVER = 'handover', 'Handover Instruction'
        FINANCIAL = 'financial', 'Financial Note'

    tenancy = models.ForeignKey(
        'Tenancy',
        on_delete=models.CASCADE,
        related_name='notes',
        help_text="The tenancy this note belongs to."
    )

    note_type = models.CharField(
        'Note Type',
        max_length=20,
        choices=NoteType.choices,
        default=NoteType.GENERAL
    )

    content = models.TextField(
        'Note Content',
        help_text="The actual note, instruction, or record of conversation."
    )

    is_confidential = models.BooleanField(
        'Is Confidential', 
        default=False,
        help_text="If true, only visible to admins and the property owner/manager, not general agency staff."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tenancy_notes',
        help_text="The user who created this note."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenancy Note'
        verbose_name_plural = 'Tenancy Notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenancy', 'created_at']),
            models.Index(fields=['note_type', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.get_note_type_display()}] Note for {self.tenancy.unit.unit_code} by {self.created_by.email if self.created_by else 'Unknown'}"