from django.apps import apps

def get_effective_permissions(staff_member, property_ref=None):
    """
    Calculates the exact, effective permissions for a staff member.
    Merges their base AgencyRole permissions with any property-specific AgencyPermission overrides.
    """
    # 1. Start with the base permissions from the staff member's assigned role
    base_permissions = staff_member.role.permissions.copy() if staff_member.role and staff_member.role.permissions else {}
    
    # 2. Check for property-specific overrides
    if property_ref and staff_member.agency:
        AgencyPermission = apps.get_model('agencies', 'AgencyPermission')
        
        specific_permission = AgencyPermission.objects.filter(
            staff_member=staff_member,
            scope='property_specific',
            delegated_property__property_ref=property_ref,
            delegated_property__status='active'
        ).first()
        
        if specific_permission:
            # Override base permissions with specific ones
            base_permissions.update(specific_permission.permissions)
            
    return base_permissions


def has_permission(staff_member, permission_key: str, property_ref=None) -> bool:
    """
    Quick boolean check if a staff member has a specific permission.
    """
    effective_perms = get_effective_permissions(staff_member, property_ref)
    return effective_perms.get(permission_key, False)


def get_delegation_details(delegated_property):
    """
    Formats the delegated property with its effective permissions for frontend display.
    NOTE: 'can_collect_payments' is intentionally excluded. All payments route strictly 
    to the verified Agency/Landlord PaymentAccount to prevent staff fraud.
    """
    # Default administrative permissions based on DelegationType
    default_perms = {
        'full': {
            'can_manage_tenants': True,
            'can_generate_invoices': True,       # Can create the bill
            'can_reconcile_payments': True,      # Can mark cash/manual payments as received
            'can_view_financials': True,         # Can see the ledger
            'can_manage_maintenance': True,
            'can_edit_listings': True
        },
        'partial': {
            'can_manage_tenants': True,
            'can_generate_invoices': True,
            'can_reconcile_payments': False,     # Cannot mark payments as received (Manager only)
            'can_view_financials': True,
            'can_manage_maintenance': True,
            'can_edit_listings': False
        },
        'view_only': {
            'can_manage_tenants': False,
            'can_generate_invoices': False,
            'can_reconcile_payments': False,
            'can_view_financials': True,         # Can only view reports
            'can_manage_maintenance': False,
            'can_edit_listings': False
        }
    }
    
    base_perms = default_perms.get(delegated_property.delegation_type, default_perms['view_only']).copy()
    
    # Apply custom overrides (if the landlord explicitly granted/revoked something)
    if delegated_property.custom_permissions:
        base_perms.update(delegated_property.custom_permissions)
        
    return {
        'property_id': delegated_property.property_ref.id,
        'property_name': delegated_property.property_ref.title,
        'delegation_type': delegated_property.delegation_type,
        'status': delegated_property.status,
        'effective_permissions': base_perms
    }