from django.db import models
from django.conf import settings

class ApplicationDecision(models.Model):
    """
    Stores the final decision on an application, including who made it 
    (Agent or Manager) and why. Critical for the escalation workflow.
    """
    class DecisionType(models.TextChoices):
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        ESCALATED = 'escalated', 'Escalated to Manager'

    application = models.OneToOneField(
        'Application',
        on_delete=models.CASCADE,
        related_name='decision',
        help_text="The application this decision applies to."
    )

    decision = models.CharField(
        'Decision',
        max_length=20,
        choices=DecisionType.choices
    )

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='application_decisions_made',
        help_text="The Agent, Manager, or Landlord who made this decision."
    )

    approver_role = models.CharField(
        'Approver Role at Time of Decision',
        max_length=20,
        help_text="e.g., 'agent', 'manager', 'landlord'. Stored for historical audit."
    )

    reason = models.TextField(
        'Decision Reason',
        blank=True,
        null=True,
        help_text="Justification for approval, rejection, or escalation."
    )

    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Application Decision'
        verbose_name_plural = 'Application Decisions'
        ordering = ['-decided_at']

    def __str__(self):
        return f"Decision: {self.get_decision_display()} for {self.application.unit.unit_code if self.application.unit else 'Property'} by {self.approver_role}"