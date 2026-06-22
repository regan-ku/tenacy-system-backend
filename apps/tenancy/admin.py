from django.contrib import admin
from .models import (
    Tenancy, Occupancy, TenancyHistory, TenancyAgreement,
    TenancyTransfer, TenancyTermination, MoveInOutRecord,
    TenancyWaiver, TenancyExtension, TenancyNote
)

@admin.register(Tenancy)
class TenancyAdmin(admin.ModelAdmin):
    list_display = ('tenant_email', 'unit_code', 'property_title', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'tenancy_type', 'start_date')
    search_fields = ('tenant__email', 'unit__unit_code', 'property__title')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('tenant', 'unit', 'property', 'created_by')

    def tenant_email(self, obj):
        return obj.tenant.email
    tenant_email.short_description = 'Tenant'

    def unit_code(self, obj):
        return obj.unit.unit_code
    unit_code.short_description = 'Unit'

    def property_title(self, obj):
        return obj.property.title
    property_title.short_description = 'Property'


@admin.register(Occupancy)
class OccupancyAdmin(admin.ModelAdmin):
    list_display = ('unit_code', 'is_occupied', 'current_tenant_email', 'occupancy_start_date')
    list_filter = ('is_occupied',)
    search_fields = ('unit__unit_code', 'current_tenant__email')
    raw_id_fields = ('unit', 'current_tenant', 'active_tenancy')

    def unit_code(self, obj):
        return obj.unit.unit_code
    unit_code.short_description = 'Unit'

    def current_tenant_email(self, obj):
        return obj.current_tenant.email if obj.current_tenant else 'N/A'
    current_tenant_email.short_description = 'Current Tenant'


@admin.register(TenancyHistory)
class TenancyHistoryAdmin(admin.ModelAdmin):
    list_display = ('tenant_email', 'unit_code', 'start_date', 'end_date', 'final_status')
    list_filter = ('final_status', 'start_date')
    search_fields = ('tenant__email', 'unit__unit_code')
    readonly_fields = ('recorded_at',)

    def tenant_email(self, obj):
        return obj.tenant.email
    tenant_email.short_description = 'Tenant'

    def unit_code(self, obj):
        return obj.unit.unit_code
    unit_code.short_description = 'Unit'


@admin.register(TenancyAgreement)
class TenancyAgreementAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'agreement_type', 'status', 'start_date', 'end_date')
    list_filter = ('agreement_type', 'status')
    search_fields = ('tenancy__unit__unit_code',)


@admin.register(TenancyTransfer)
class TenancyTransferAdmin(admin.ModelAdmin):
    list_display = ('tenant_email', 'from_unit_code', 'to_unit_code', 'transfer_status', 'requested_at')
    list_filter = ('transfer_status', 'requested_at')
    search_fields = ('tenant__email', 'from_unit__unit_code', 'to_unit__unit_code')
    readonly_fields = ('requested_at', 'processed_at')

    def tenant_email(self, obj):
        return obj.tenant.email
    tenant_email.short_description = 'Tenant'

    def from_unit_code(self, obj):
        return obj.from_unit.unit_code
    from_unit_code.short_description = 'From Unit'

    def to_unit_code(self, obj):
        return obj.to_unit.unit_code
    to_unit_code.short_description = 'To Unit'


@admin.register(TenancyTermination)
class TenancyTerminationAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'termination_type', 'effective_date', 'penalty_applied', 'approved_by_email')
    list_filter = ('termination_type', 'effective_date')
    search_fields = ('tenancy__unit__unit_code', 'notes')
    readonly_fields = ('created_at',)

    def approved_by_email(self, obj):
        return obj.approved_by.email if obj.approved_by else 'N/A'
    approved_by_email.short_description = 'Approved By'


@admin.register(MoveInOutRecord)
class MoveInOutRecordAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'event_type', 'scheduled_date', 'actual_date', 'keys_handed_over')
    list_filter = ('event_type', 'keys_handed_over', 'utilities_transferred')
    search_fields = ('tenancy__unit__unit_code',)


@admin.register(TenancyWaiver)
class TenancyWaiverAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'waiver_type', 'status', 'requested_at', 'approved_by_email')
    list_filter = ('waiver_type', 'status')
    readonly_fields = ('requested_at', 'processed_at')

    def approved_by_email(self, obj):
        return obj.approved_by.email if obj.approved_by else 'N/A'
    approved_by_email.short_description = 'Approved By'


@admin.register(TenancyExtension)
class TenancyExtensionAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'requested_new_end_date', 'proposed_rent_adjustment', 'status', 'requested_at')
    list_filter = ('status', 'requested_at')
    readonly_fields = ('requested_at', 'processed_at')


@admin.register(TenancyNote)
class TenancyNoteAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'note_type', 'is_confidential', 'created_by_email', 'created_at')
    list_filter = ('note_type', 'is_confidential', 'created_at')
    search_fields = ('content', 'tenancy__unit__unit_code')
    readonly_fields = ('created_at', 'updated_at')

    def created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else 'System'
    created_by_email.short_description = 'Created By'