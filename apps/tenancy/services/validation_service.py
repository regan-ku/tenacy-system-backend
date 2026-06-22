from django.core.exceptions import ValidationError
from ..models import Tenancy, Occupancy, TenancyTransfer
from ..utils.tenancy_utils import TenancyUtils

class TenancyValidationService:
    """
    Enforces strict business rules for tenancy creation, transfers, and terminations.
    Prevents invalid states from ever reaching the database.
    """

    @staticmethod
    def validate_unit_availability(unit) -> None:
        """
        CRITICAL RULE: 1 Unit = 1 Active Tenancy only.
        Prevents double-booking or assigning a tenant to an already occupied unit.
        """
        if hasattr(unit, 'occupancy_record') and unit.occupancy_record.is_occupied:
            raise ValidationError(f"Unit {unit.unit_code} is currently occupied and cannot be assigned.")
            
        # Double-check via active tenancies
        active_tenancies = Tenancy.objects.filter(
            unit=unit, 
            status__in=['pending_payment', 'active', 'extended']
        )
        if active_tenancies.exists():
            raise ValidationError(f"Unit {unit.unit_code} already has an active tenancy.")

    @staticmethod
    def validate_tenant_eligibility(tenant, property_obj) -> None:
        """
        Checks if a tenant is eligible to rent in this specific property.
        (e.g., checking for active blacklists or conflicting active tenancies in the same building, if applicable).
        """
        # Future: Add blacklist check here
        pass

    @staticmethod
    def validate_activation_readiness(tenancy) -> None:
        """
        Ensures a tenancy can only become ACTIVE if financial prerequisites are met.
        Rule: Deposit AND Service Charge must be paid OR waived.
        """
        if not tenancy.is_ready_for_activation():
            raise ValidationError(
                "Tenancy cannot be activated. Deposit and Service Charge must be marked as paid or waived."
            )

    @staticmethod
    def validate_transfer_request(transfer_request: TenancyTransfer) -> None:
        """
        Validates that a tenant transfer between units/properties is legally and operationally sound.
        """
        # 1. Source unit must have an active tenancy for this tenant
        source_tenancy = Tenancy.objects.filter(
            tenant=transfer_request.tenant,
            unit=transfer_request.from_unit,
            status__in=['active', 'extended']
        ).first()
        
        if not source_tenancy:
            raise ValidationError("No active tenancy found for the source unit.")

        # 2. Destination unit must be available
        TenancyValidationService.validate_unit_availability(transfer_request.to_unit)

        # 3. Tenant cannot transfer to a unit in the same property if it violates capacity (optional business rule)
        if transfer_request.from_property == transfer_request.to_property:
            if transfer_request.from_unit == transfer_request.to_unit:
                raise ValidationError("Source and destination units cannot be the same.")