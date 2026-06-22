from django.db import models
from django.conf import settings

class AgencyActivityLog(models.Model):
    """
    Immutable audit log for all critical actions within an agency.
    Essential for compliance, dispute resolution, and security tracking.
    """
    class ActionType(models.TextChoices):
        STAFF_CREATED = 'staff_created', 'Staff Member Created'
        STAFF_ROLE_CHANGED = 'staff_role_changed', 'Staff Role Changed'
        DELEGATION_GRANTED = 'delegation_granted', 'Property Delegation Granted'
        DELEGATION_REVOKED = 'delegation_revoked', 'Property Delegation Revoked'
        VERIFICATION_SUBMITTED = 'verification_submitted', 'Verification Documents Submitted'
        VERIFICATION_APPROVED = 'verification_approved', 'Verification Approved by Admin'
        VERIFICATION_REJECTED = 'verification_rejected', 'Verification Rejected by Admin'

    agency = models.ForeignKey(
        'Agency',
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    action_type = models.CharField(
        'Action Type',
        max_length=30,
        choices=ActionType.choices
    )
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='agency_actions_performed'
    )
    
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_actions_targeted',
        help_text="The user this action was performed on (if applicable)."
    )
    
    details = models.JSONField(
        'Action Details',
        default=dict,
        help_text="Structured data about the action (e.g., old_role, new_role, property_id)."
    )
    
    ip_address = models.GenericIPAddressField('IP Address', blank=True, null=True)
    timestamp = models.DateTimeField('Timestamp', auto_now_add=True)

    class Meta:
        verbose_name = 'Agency Activity Log'
        verbose_name_plural = 'Agency Activity Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['agency', 'timestamp']),
            models.Index(fields=['performed_by', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.get_action_type_display()} by {self.performed_by}"