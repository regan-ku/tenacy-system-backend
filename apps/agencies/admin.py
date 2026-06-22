from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Agency, AgencyDirector, AgencyVerification, AgencyProfile,
    AgencyStaff, AgencyRole, DelegatedProperty, AgencyPermission, AgencyActivityLog
)
from .services import AgencyVerificationService, DirectorService

# ---------------------------------------------------------
# 1. AGENCY ADMIN
# ---------------------------------------------------------
@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'contact_email', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active', 'created_at')
    search_fields = ('name', 'registration_number', 'contact_email')
    readonly_fields = ('created_at', 'updated_at')

# ---------------------------------------------------------
# 2. AGENCY DIRECTOR ADMIN
# ---------------------------------------------------------
@admin.register(AgencyDirector)
class AgencyDirectorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'agency_name', 'national_id', 'verification_status', 'is_primary_director')
    list_filter = ('verification_status', 'is_primary_director')
    search_fields = ('full_name', 'national_id', 'passport_number', 'agency__name')
    readonly_fields = ('created_at', 'updated_at')

    def agency_name(self, obj):
        return obj.agency.name
    agency_name.short_description = 'Agency'

    actions = ['approve_directors', 'reject_directors']

    @admin.action(description="Approve selected directors")
    def approve_directors(self, request, queryset):
        for director in queryset.filter(verification_status='pending'):
            DirectorService.verify_director(director, request.user, 'verified')
        self.message_user(request, f"Successfully approved {queryset.count()} directors.")

    @admin.action(description="Reject selected directors")
    def reject_directors(self, request, queryset):
        for director in queryset.filter(verification_status__in=['pending', 'verified']):
            DirectorService.verify_director(director, request.user, 'rejected', "Rejected via admin bulk action.")
        self.message_user(request, f"Successfully rejected {queryset.count()} directors.")

# ---------------------------------------------------------
# 3. AGENCY VERIFICATION ADMIN
# ---------------------------------------------------------
@admin.register(AgencyVerification)
class AgencyVerificationAdmin(admin.ModelAdmin):
    list_display = ('agency_name', 'status', 'submitted_at', 'reviewed_by_link')
    list_filter = ('status', 'submitted_at')
    search_fields = ('agency__name', 'kra_pin')
    readonly_fields = ('submitted_at', 'reviewed_at', 'reviewed_by', 'status', 'rejection_reason')

    def agency_name(self, obj):
        return obj.agency.name
    agency_name.short_description = 'Agency'

    def reviewed_by_link(self, obj):
        return obj.reviewed_by.email if obj.reviewed_by else format_html('<span style="color: orange;">Pending</span>')
    reviewed_by_link.short_description = 'Reviewed By'

    actions = ['approve_verifications', 'reject_verifications']

    @admin.action(description="Approve selected agency verifications")
    def approve_verifications(self, request, queryset):
        for verification in queryset.filter(status__in=['pending', 'resubmit']):
            AgencyVerificationService.review_business_verification(verification, request.user, 'verified')
        self.message_user(request, f"Successfully approved {queryset.count()} agency verifications.")

    @admin.action(description="Reject selected agency verifications")
    def reject_verifications(self, request, queryset):
        for verification in queryset.filter(status__in=['pending', 'verified']):
            AgencyVerificationService.review_business_verification(
                verification, request.user, 'rejected', "Rejected via admin bulk action. Please check requirements."
            )
        self.message_user(request, f"Successfully rejected {queryset.count()} agency verifications.")

# ---------------------------------------------------------
# 4. DELEGATED PROPERTY ADMIN
# ---------------------------------------------------------
@admin.register(DelegatedProperty)
class DelegatedPropertyAdmin(admin.ModelAdmin):
    list_display = ('property_ref', 'agency_name', 'delegation_type', 'status', 'start_date')
    list_filter = ('status', 'delegation_type', 'start_date')
    search_fields = ('property_ref__title', 'agency__name')
    readonly_fields = ('created_at', 'updated_at', 'revoked_at', 'revoked_by')

    def agency_name(self, obj):
        return obj.agency.name
    agency_name.short_description = 'Agency'

# ---------------------------------------------------------
# 5. AGENCY ACTIVITY LOG ADMIN (Read-Only Audit Trail)
# ---------------------------------------------------------
@admin.register(AgencyActivityLog)
class AgencyActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'agency_name', 'action_type', 'performed_by_email', 'target_user_email')
    list_filter = ('action_type', 'timestamp')
    search_fields = ('agency__name', 'performed_by__email', 'target_user__email')
    readonly_fields = ('agency', 'action_type', 'performed_by', 'target_user', 'details', 'ip_address', 'timestamp')

    def agency_name(self, obj):
        return obj.agency.name
    agency_name.short_description = 'Agency'

    def performed_by_email(self, obj):
        return obj.performed_by.email if obj.performed_by else 'System'
    performed_by_email.short_description = 'Performed By'

    def target_user_email(self, obj):
        return obj.target_user.email if obj.target_user else 'N/A'
    target_user_email.short_description = 'Target User'

# Register remaining models with basic admin config
admin.site.register(AgencyProfile)
admin.site.register(AgencyStaff)
admin.site.register(AgencyRole)
admin.site.register(AgencyPermission)