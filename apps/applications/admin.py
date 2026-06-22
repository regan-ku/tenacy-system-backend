from django.contrib import admin
from .models import (
    Application, RentalApplication, TransferApplication, 
    EvictionApplication, ApplicationNote, ApplicationDecision
)

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant_email', 'application_type', 'property_title', 'unit_code', 'status', 'created_at')
    list_filter = ('application_type', 'status', 'created_at')
    search_fields = ('applicant__email', 'property__title', 'unit__unit_code')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('applicant', 'property', 'unit')

    def applicant_email(self, obj):
        return obj.applicant.email
    applicant_email.short_description = 'Applicant'

    def property_title(self, obj):
        return obj.property.title
    property_title.short_description = 'Property'

    def unit_code(self, obj):
        return obj.unit.unit_code if obj.unit else 'N/A'
    unit_code.short_description = 'Unit'

@admin.register(RentalApplication)
class RentalApplicationAdmin(admin.ModelAdmin):
    list_display = ('application', 'employment_status', 'desired_move_in_date', 'meets_deposit_requirement', 'has_blocking_flags')
    list_filter = ('employment_status', 'meets_deposit_requirement', 'has_blocking_flags')
    search_fields = ('application__applicant__email',)
    raw_id_fields = ('application',)

@admin.register(TransferApplication)
class TransferApplicationAdmin(admin.ModelAdmin):
    list_display = ('application', 'from_unit_code', 'to_unit_code', 'has_unpaid_critical_arrears', 'transfer_allowed_by_permissions')
    list_filter = ('has_unpaid_critical_arrears', 'transfer_allowed_by_permissions')
    search_fields = ('application__applicant__email', 'from_unit__unit_code', 'to_unit__unit_code')
    raw_id_fields = ('application', 'current_tenancy', 'from_property', 'from_unit', 'to_property', 'to_unit')

    def from_unit_code(self, obj):
        return obj.from_unit.unit_code
    from_unit_code.short_description = 'From Unit'

    def to_unit_code(self, obj):
        return obj.to_unit.unit_code
    to_unit_code.short_description = 'To Unit'

@admin.register(EvictionApplication)
class EvictionApplicationAdmin(admin.ModelAdmin):
    list_display = ('application', 'notice_period_days', 'intended_vacate_date', 'reason_for_leaving')
    list_filter = ('notice_period_days', 'intended_vacate_date')
    search_fields = ('application__applicant__email', 'application__unit__unit_code')
    raw_id_fields = ('application',)

@admin.register(ApplicationDecision)
class ApplicationDecisionAdmin(admin.ModelAdmin):
    list_display = ('application', 'decision', 'approver_role', 'decided_at')
    list_filter = ('decision', 'approver_role', 'decided_at')
    search_fields = ('application__applicant__email', 'reason')
    readonly_fields = ('decided_at',)
    raw_id_fields = ('application', 'approver')

@admin.register(ApplicationNote)
class ApplicationNoteAdmin(admin.ModelAdmin):
    list_display = ('application', 'note_type', 'is_confidential', 'created_by_email', 'created_at')
    list_filter = ('note_type', 'is_confidential', 'created_at')
    search_fields = ('content', 'application__applicant__email')
    readonly_fields = ('created_at',)
    raw_id_fields = ('application', 'created_by')

    def created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else 'System'
    created_by_email.short_description = 'Created By'