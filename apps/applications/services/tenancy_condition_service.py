from django.core.exceptions import ValidationError
from apps.properties.models import Unit
from apps.tenancy.models import Tenancy

class TenancyConditionService:
    """
    Validates hard system rules for Rental and Transfer applications.
    If these fail, the application cannot be approved by an Agent and must be escalated or rejected.
    """

    @staticmethod
    def validate_rental_conditions(unit: Unit, tenant) -> dict:
        """
        Checks all prerequisites for a new rental application.
        Returns a dict of validation results and any blocking flags.
        """
        conditions = {
            "unit_is_available": unit.status == 'available',
            "property_is_active": unit.property.is_active,
            "tenant_has_no_active_conflict": not Tenancy.objects.filter(
                tenant=tenant, 
                unit=unit, 
                status__in=['active', 'pending_payment', 'extended']
            ).exists(),
            "has_deposit_requirement": unit.deposit_amount >= 0, 
            "has_service_charge_requirement": unit.service_charge >= 0,
        }

        # Determine if there are any hard blocking flags
        blocking_flags = not conditions["unit_is_available"] or not conditions["property_is_active"]
        
        conditions["has_blocking_flags"] = blocking_flags
        conditions["all_conditions_met"] = all(conditions.values()) and not blocking_flags
        
        return conditions

    @staticmethod
    def validate_transfer_conditions(from_unit: Unit, to_unit: Unit, tenant) -> dict:
        """
        Checks all prerequisites for a tenant transfer application.
        """
        # Check if tenant actually has an active tenancy in the source unit
        active_tenancy = Tenancy.objects.filter(
            tenant=tenant,
            unit=from_unit,
            status__in=['active', 'extended']
        ).first()

        conditions = {
            "has_active_source_tenancy": active_tenancy is not None,
            "target_unit_is_available": to_unit.status == 'available',
            "same_management_scope": from_unit.property.current_manager_id == to_unit.property.current_manager_id, # Critical rule
            "no_critical_arrears": True # Placeholder: Integrate with Payments app later to check arrears
        }

        blocking_flags = not conditions["target_unit_is_available"] or not conditions["same_management_scope"]
        
        conditions["has_blocking_flags"] = blocking_flags
        conditions["all_conditions_met"] = all(conditions.values()) and not blocking_flags
        
        return conditions