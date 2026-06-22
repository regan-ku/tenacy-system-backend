from django.db import models

class RentalApplication(models.Model):
    """
    Extends the base Application model for new tenant occupancy requests.
    User input is strictly limited to employment status and move-in date.
    All other details (name, phone, unit price) are auto-populated via FKs.
    """
    application = models.OneToOneField(
        'Application',
        on_delete=models.CASCADE,
        related_name='rental_details',
        help_text="The base application record this rental request extends."
    )

    # ONLY USER-INPUT FIELDS
    employment_status = models.CharField(
        'Employment Status', 
        max_length=20, 
        choices=[
            ('employed', 'Employed'),
            ('self_employed', 'Self Employed'),
            ('student', 'Student'),
            ('unemployed', 'Unemployed')
        ],
        help_text="Current employment status of the applicant."
    )

    desired_move_in_date = models.DateField(
        'Desired Move-in Date',
        help_text="The date the applicant wishes to occupy the unit."
    )

    # System Validation Flags (Populated by TenancyConditionService)
    meets_deposit_requirement = models.BooleanField('Meets Deposit Requirement', default=False)
    meets_service_charge_requirement = models.BooleanField('Meets Service Charge Requirement', default=False)
    has_blocking_flags = models.BooleanField('Has Blocking Flags (e.g., arrears)', default=False)

    class Meta:
        verbose_name = 'Rental Application'
        verbose_name_plural = 'Rental Applications'

    def __str__(self):
        return f"Rental Application for {self.application.unit.unit_code}"