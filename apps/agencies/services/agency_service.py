from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import Agency, AgencyDirector, AgencyVerification, AgencyActivityLog
from ..utils.validation_utils import validate_agency_activation

class AgencyService:
    """
    Core business logic for Agency lifecycle management.
    """

    @staticmethod
    @transaction.atomic
    def create_agency(created_by_user, name: str, registration_number: str, contact_email: str, phone_number: str, physical_address: str) -> Agency:
        """Creates a new agency in pending state."""
        if Agency.objects.filter(registration_number=registration_number).exists():
            raise ValidationError("An agency with this registration number already exists.")
        if Agency.objects.filter(contact_email=contact_email.lower()).exists():
            raise ValidationError("An agency with this contact email already exists.")

        agency = Agency.objects.create(
            created_by=created_by_user,
            name=name,
            registration_number=registration_number,
            contact_email=contact_email.lower(),
            phone_number=phone_number,
            physical_address=physical_address,
            status=Agency.Status.PENDING_VERIFICATION
        )
        AgencyVerification.objects.create(agency=agency)
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.VERIFICATION_SUBMITTED,
            performed_by=created_by_user,
            details={"status": "pending_verification", "step": "agency_created"}
        )
        return agency

    @staticmethod
    @transaction.atomic
    def activate_agency(agency: Agency, admin_reviewer) -> Agency:
        """Activates agency after passing all compliance checks."""
        validate_agency_activation(agency)
        
        agency.status = Agency.Status.ACTIVE
        agency.is_active = True
        agency.save(update_fields=['status', 'is_active'])
        
        AgencyActivityLog.objects.create(
            agency=agency,
            action_type=AgencyActivityLog.ActionType.VERIFICATION_APPROVED,
            performed_by=admin_reviewer,
            details={"status": "active", "activated_at": timezone.now().isoformat()}
        )
        return agency

    @staticmethod
    def get_agency_dashboard_state(agency: Agency) -> dict:
        """Resolves the operational state for the agency dashboard."""
        verification = getattr(agency, 'verification_record', None)
        is_verified = verification and verification.status == AgencyVerification.Status.VERIFIED
        has_verified_director = agency.directors.filter(verification_status=AgencyDirector.VerificationStatus.VERIFIED).exists()
        
        if agency.status != Agency.Status.ACTIVE:
            next_step = "verify_business" if not is_verified else "verify_directors"
            return {
                "is_active": False,
                "status": agency.status,
                "next_step": next_step,
                "message": "Agency verification or director validation pending."
            }

        delegated_count = agency.delegated_properties.filter(status='active').count()
        staff_count = agency.staff_members.filter(status='active').count()
        
        return {
            "is_active": True,
            "status": Agency.Status.ACTIVE,
            "delegated_properties_count": delegated_count,
            "active_staff_count": staff_count,
            "next_step": "dashboard",
            "message": "Agency is fully verified and operational."
        }