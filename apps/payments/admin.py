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
    # ✅ ADDED: verification_status to list_display and list_filter
    list_display = ("account_name", "get_account_type_display", "owner", "verification_status", "is_verified", "is_active", "is_default", "created_at")
    list_filter = ("account_type", "verification_status", "is_verified", "is_active", "created_at")
    search_fields = ("account_name", "paybill_number", "till_number", "phone_number")
    readonly_fields = ("created_at", "updated_at")
    actions = ["activate_selected", "deactivate_selected"]

    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
    activate_selected.short_description = "Activate selected accounts"
    
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_selected.short_description = "Deactivate selected accounts"


# ✅ NEW: Register PaymentAccountVerification with Approval Actions
@admin.register(PaymentAccountVerification)
class PaymentAccountVerificationAdmin(admin.ModelAdmin):
    list_display = ("payment_account", "method", "status", "requested_by", "created_at")
    list_filter = ("status", "method")
    search_fields = ("payment_account__account_name", "reference")
    readonly_fields = ("created_at",)
    
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        for ver in queryset:
            ver.status = "verified"
            ver.verified_at = timezone.now()
            ver.save()
            
            # ✅ Sync the approval back to the parent Payment Account
            ver.payment_account.is_verified = True
            ver.payment_account.verification_status = "verified"
            ver.payment_account.save(update_fields=["is_verified", "verification_status"])
            
    approve_selected.short_description = "✅ Approve selected verifications"

    def reject_selected(self, request, queryset):
        for ver in queryset:
            ver.status = "rejected"
            ver.save()
            
            # ✅ Sync the rejection back to the parent Payment Account
            ver.payment_account.verification_status = "rejected"
            ver.payment_account.save(update_fields=["verification_status"])
            
    reject_selected.short_description = "❌ Reject selected verifications"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id_short", "invoice_number", "tenancy", "total_amount", "balance_due", "status", "due_date", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("invoice_number", "tenancy__tenancy_code")
    readonly_fields = ("id", "invoice_number", "amount_paid", "balance_due", "created_at", "updated_at")
    inlines = [InvoiceItemInline]

    def id_short(self, obj): return str(obj.id)[:8]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_id", "amount", "source", "status", "payer", "paid_at", "created_at")
    list_filter = ("source", "status", "created_at")
    search_fields = ("payment_id", "payer__email")
    readonly_fields = ("id", "raw_payload", "paid_at", "created_at")
    inlines = [PaymentAllocationInline, ReconciliationInline]

@admin.register(Arrears)
class ArrearsAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "total_outstanding", "days_overdue", "status", "last_updated")
    list_filter = ("status", "last_updated")
    search_fields = ("tenancy__tenancy_code", "tenancy__tenant__email")
    readonly_fields = ("last_updated",)

@admin.register(Waiver)
class WaiverAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "amount", "approved_by", "reason", "created_at")
    search_fields = ("tenancy__tenancy_code", "reason")
    readonly_fields = ("created_at",)

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "amount", "status", "requested_by", "processed_at", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("processed_at", "created_at")

@admin.register(TenantBalance)
class TenantBalanceAdmin(admin.ModelAdmin):
    list_display = ("tenancy", "total_invoiced", "total_paid", "current_balance", "last_updated")
    search_fields = ("tenancy__tenancy_code",)
    readonly_fields = ("last_updated",)