from django.contrib import admin
from django.utils import timezone
from .models import (
    PaymentAccount, PaymentAccountVerification, Invoice, InvoiceItem,
    Payment, PaymentAllocation, Receipt, Arrears, Waiver, Refund,
    TenantBalance, Reconciliation
)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("created_at",)


class PaymentAllocationInline(admin.StackedInline):
    model = PaymentAllocation
    extra = 0
    readonly_fields = ("created_at",)


class ReconciliationInline(admin.StackedInline):
    model = Reconciliation
    extra = 0
    readonly_fields = ("reconciled_at",)


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    """
    PLATFORM SETTLEMENT MODEL:
    Admin interface for managing landlord/agency settlement accounts.
    These accounts receive payouts from the platform, NOT tenant payments.
    """
    list_display = (
        "account_name", "get_account_type_display", "owner",
        "verification_status", "is_verified", "is_active",
        "is_default", "created_at"
    )
    list_filter = ("account_type", "verification_status", "is_verified", "is_active", "created_at")
    search_fields = ("account_name", "paybill_number", "till_number", "phone_number")
    readonly_fields = ("created_at", "updated_at")

    # Note: Manual activation kept for emergency admin overrides only.
    # Primary flow should be via the Verification approval action below.
    actions = ["activate_selected", "deactivate_selected", "suspend_selected"]

    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
    activate_selected.short_description = "✅ Activate selected accounts"

    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_selected.short_description = "⏸️ Deactivate selected accounts"

    def suspend_selected(self, request, queryset):
        queryset.update(is_active=False, verification_status="suspended")
    suspend_selected.short_description = "🚫 Suspend selected accounts (fraud/compliance)"


@admin.register(PaymentAccountVerification)
class PaymentAccountVerificationAdmin(admin.ModelAdmin):
    """
    PLATFORM SETTLEMENT MODEL:
    Admin interface for verifying settlement accounts before payouts.

    ✅ FIELD NAMES CORRECTED to match the PaymentAccountVerification model:
    - method (NOT verification_method)
    - status (NOT verification_status)
    - reference (NOT verification_reference)
    - verified_at (NOT verification_timestamp)
    - notes (NOT verification_notes)
    """
    list_display = ("payment_account", "method", "status", "requested_by", "verified_by", "created_at")
    list_filter = ("status", "method")
    search_fields = ("payment_account__account_name", "reference")
    readonly_fields = ("created_at",)

    actions = ["approve_selected", "reject_selected", "suspend_selected"]

    def approve_selected(self, request, queryset):
        for ver in queryset.filter(status="pending"):
            ver.status = "verified"
            ver.verified_by = request.user  # ✅ Audit trail
            ver.verified_at = timezone.now()
            ver.save()  # Model's save() auto-syncs is_verified + verification_status to parent

            # ✅ Activate the account for payouts
            # (model's save() doesn't handle is_active, so we do it here)
            account = ver.payment_account
            if not account.is_active:
                account.is_active = True
                account.save(update_fields=["is_active"])

    approve_selected.short_description = "✅ Approve and Activate Settlement Account"

    def reject_selected(self, request, queryset):
        for ver in queryset.filter(status="pending"):
            ver.status = "rejected"
            ver.verified_by = request.user  # ✅ Audit trail
            ver.verified_at = timezone.now()
            ver.save()  # Model's save() auto-syncs rejection to parent

            # ✅ Ensure account is deactivated on rejection
            account = ver.payment_account
            if account.is_active:
                account.is_active = False
                account.save(update_fields=["is_active"])

    reject_selected.short_description = "❌ Reject selected verifications"

    def suspend_selected(self, request, queryset):
        for ver in queryset.filter(status="verified"):
            ver.status = "suspended"
            ver.verified_by = request.user
            ver.save()

            # ✅ Deactivate account on suspension
            account = ver.payment_account
            account.is_active = False
            account.verification_status = "suspended"
            account.save(update_fields=["is_active", "verification_status"])

    suspend_selected.short_description = "🚫 Suspend selected accounts"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id_short", "invoice_number", "tenancy", "total_amount", "balance_due", "status", "due_date", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("invoice_number", "tenancy__tenant__email")
    readonly_fields = ("id", "invoice_number", "amount_paid", "balance_due", "created_at", "updated_at")
    inlines = [InvoiceItemInline]

    def id_short(self, obj):
        return str(obj.id)[:8]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    PLATFORM COLLECTION MODEL:
    Shows account_reference and tenancy for reconciliation tracking.
    """
    list_display = ("payment_id", "amount", "source", "status", "payer", "account_reference", "paid_at", "created_at")
    list_filter = ("source", "status", "created_at")
    search_fields = ("payment_id", "payer__email", "account_reference")
    readonly_fields = ("id", "tenancy", "raw_payload", "paid_at", "created_at")
    inlines = [PaymentAllocationInline, ReconciliationInline]


@admin.register(Arrears)
class ArrearsAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "total_outstanding", "days_overdue", "status", "last_updated")
    list_filter = ("status", "last_updated")
    search_fields = ("tenancy__tenant__email",)
    readonly_fields = ("last_updated",)


@admin.register(Waiver)
class WaiverAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "amount", "approved_by", "reason", "created_at")
    search_fields = ("tenancy__tenant__email", "reason")
    readonly_fields = ("created_at",)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "amount", "status", "requested_by", "processed_at", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("processed_at", "created_at")


@admin.register(TenantBalance)
class TenantBalanceAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "total_invoiced", "total_paid", "current_balance", "last_updated")
    search_fields = ("tenancy__tenant__email",)
    readonly_fields = ("last_updated",)