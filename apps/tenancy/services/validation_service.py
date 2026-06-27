from django.core.exceptions import ValidationError
from ..models import Tenancy, Occupancy, TenancyTransfer

class TenancyValidationService:
    """
    Enforces strict business rules for tenancy creation, transfers, and terminations.
    Prevents invalid states from ever reaching the database.
    
    Core Rules:
    - 1 Unit = 1 Active Tenancy only
    - Transfers only allowed within same management (same landlord/agency)
    - Tenancy activation requires deposit + service charge paid/waived
    """

    @staticmethod
    def validate_unit_availability(unit) -> None:
        """
        CRITICAL RULE: 1 Unit = 1 Active Tenancy only.
        Prevents double-booking or assigning a tenant to an already occupied unit.
        """
        # Check occupancy record first
        if hasattr(unit, 'occupancy_record') and unit.occupancy_record.is_occupied:
            raise ValidationError(f"Unit {unit.unit_code} is currently occupied and cannot be assigned.")
            
        # Double-check via active tenancies (source of truth)
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
        Currently a placeholder for future blacklist/eligibility checks.
        """
        # Future: Add blacklist check here
        # Future: Check if tenant already has too many active tenancies
        # Future: Check tenant's payment history
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

        # 3. Tenant cannot transfer to the same unit
        if transfer_request.from_unit == transfer_request.to_unit:
            raise ValidationError("Source and destination units cannot be the same.")

        # 4. ✅ CRITICAL: Both properties must be under the same management
        TenancyValidationService.validate_same_management(
            transfer_request.from_property, 
            transfer_request.to_property
        )

    @staticmethod
    def validate_same_management(from_property, to_property) -> None:
        """
        CRITICAL RULE: Transfers are ONLY allowed between properties under the EXACT SAME management.
        Both properties must share the same owner (created_by) AND the same current manager.
        Prevents cross-agency/cross-landlord transfers.
        """
        if from_property.created_by_id != to_property.created_by_id:
            raise ValidationError(
                "Transfers are only allowed between properties owned by the same landlord."
            )
            
        if from_property.current_manager_id != to_property.current_manager_id:
            raise ValidationError(
                "Transfers are only allowed between properties managed by the same entity (landlord or agency)."
            )

    @staticmethod
    def validate_termination_request(tenancy, termination_type: str) -> None:
        """
        Validates that a termination request is valid for the given tenancy.
        """
        if tenancy.status in [Tenancy.Status.TERMINATED, Tenancy.Status.EXPIRED]:
            raise ValidationError(
                f"Cannot terminate a tenancy with status '{tenancy.status}'."
            )
        
        valid_types = ['tenant_request', 'landlord_request', 'breach', 'expiry', 'mutual']
        if termination_type not in valid_types:
            raise ValidationError(
                f"Invalid termination type '{termination_type}'. Must be one of: {', '.join(valid_types)}"
            )

    @staticmethod
    def validate_extension_request(tenancy, new_end_date) -> None:
        """
        Validates that an extension request is valid.
        """
        from django.utils import timezone
        
        if tenancy.status not in [Tenancy.Status.ACTIVE, Tenancy.Status.EXTENDED]:
            raise ValidationError(
                f"Cannot extend a tenancy with status '{tenancy.status}'. Must be active or extended."
            )
        
        if new_end_date <= timezone.now().date():
            raise ValidationError("New end date must be in the future.")
        
        if tenancy.end_date and new_end_date <= tenancy.end_date:
            raise ValidationError("New end date must be after the current end date.")