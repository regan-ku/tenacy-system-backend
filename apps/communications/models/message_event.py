import uuid
from django.db import models

class EventType(models.TextChoices):
    TENANCY_CREATED = "tenancy_created", "Tenancy Created"
    TENANCY_TERMINATED = "tenancy_terminated", "Tenancy Terminated"
    PAYMENT_RECEIVED = "payment_received", "Payment Received"
    INVOICE_GENERATED = "invoice_generated", "Invoice Generated"
    APPLICATION_APPROVED = "application_approved", "Application Approved"
    APPLICATION_REJECTED = "application_rejected", "Application Rejected"
    MAINTENANCE_UPDATED = "maintenance_updated", "Maintenance Updated"
    ARREARS_ALERT = "arrears_alert", "Arrears Alert"

class MessageEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    target_user_id = models.UUIDField(null=True, blank=True, help_text="Recipient user ID")
    payload = models.JSONField(default=dict, help_text="Dynamic data for template injection")
    processed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event_type", "processed"])]

    def __str__(self):
        return f"{self.get_event_type_display()} | {'✅' if self.processed else '⏳'}"