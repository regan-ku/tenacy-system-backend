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
        """
        # ✅ FIX: Safely extract the property object (handles 'property_ref' or 'property')
        property_obj = getattr(unit, 'property_ref', None) or getattr(unit, 'property', None)
        property_is_active = property_obj.is_active if property_obj else False

        conditions = {
            "unit_is_available": unit.status == 'available',
            "property_is_active": property_is_active,
            "tenant_has_no_active_conflict": not Tenancy.objects.filter(
                tenant=tenant, 
                unit=unit, 
                status__in=['active', 'pending_payment', 'extended']
            ).exists(),
            "has_deposit_requirement": getattr(unit, 'deposit_amount', 0) >= 0, 
            "has_service_charge_requirement": getattr(unit, 'service_charge', 0) >= 0,
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
        active_tenancy = Tenancy.objects.filter(
            tenant=tenant,
            unit=from_unit,
            status__in=['active', 'extended']
        ).first()

        # ✅ FIX: Safely extract property objects
        from_property = getattr(from_unit, 'property_ref', None) or getattr(from_unit, 'property', None)
        to_property = getattr(to_unit, 'property_ref', None) or getattr(to_unit, 'property', None)

        same_management = False
        if from_property and to_property:
            same_management = getattr(from_property, 'current_manager_id', None) == getattr(to_property, 'current_manager_id', None)

        conditions = {
            "has_active_source_tenancy": active_tenancy is not None,
            "target_unit_is_available": to_unit.status == 'available',
            "same_management_scope": same_management,
            "no_critical_arrears": True # Placeholder for Payments app integration
        }

        blocking_flags = not conditions["target_unit_is_available"] or not conditions["same_management_scope"]
        
        conditions["has_blocking_flags"] = blocking_flags
        conditions["all_conditions_met"] = all(conditions.values()) and not blocking_flags
        
        return conditions