from django.contrib import admin
from .models import (
    DocumentType, DocumentTemplate, Document, DocumentVersion,
    DocumentAttachment, DocumentAuditLog, GeneratedDocument
)

class DocumentVersionInline(admin.StackedInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ("created_at",)

class DocumentAttachmentInline(admin.TabularInline):
    model = DocumentAttachment
    extra = 0
    readonly_fields = ("created_at",)

class DocumentAuditLogInline(admin.StackedInline):
    model = DocumentAuditLog
    extra = 0
    readonly_fields = ("metadata", "created_at")
    can_delete = False

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "requires_signature", "is_active")
    list_filter = ("is_active", "requires_signature")
    search_fields = ("name", "code")

@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "document_type", "is_default", "is_active", "updated_at")
    list_filter = ("document_type", "is_active", "is_default")
    search_fields = ("name",)
    readonly_fields = ("updated_at",)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "status", "assigned_to", "expires_at", "created_at")
    list_filter = ("status", "document_type", "created_at")
    search_fields = ("title", "metadata")
    readonly_fields = ("id", "file_url", "created_at", "updated_at")
    inlines = [DocumentVersionInline, DocumentAttachmentInline, DocumentAuditLogInline]
    actions = ["mark_archived", "mark_active"]

    def mark_archived(self, request, queryset):
        queryset.update(status="archived")
    mark_archived.short_description = "Mark selected as archived"

    def mark_active(self, request, queryset):
        queryset.update(status="active")
    mark_active.short_description = "Mark selected as active"

@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ("document", "template", "status", "generated_at", "checksum")
    list_filter = ("status", "generated_at")
    search_fields = ("document__title",)
    readonly_fields = ("id", "generation_variables", "checksum", "file_size", "page_count", "generated_at")

@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("document", "version_number", "changed_by", "change_reason", "created_at")
    list_filter = ("created_at",)
    search_fields = ("document__title", "change_reason")
    readonly_fields = ("id", "created_at")

@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(admin.ModelAdmin):
    list_display = ("document", "file_type", "caption", "uploaded_by", "created_at")
    list_filter = ("file_type",)
    readonly_fields = ("id", "file_url", "created_at")

@admin.register(DocumentAuditLog)
class DocumentAuditLogAdmin(admin.ModelAdmin):
    list_display = ("document", "action", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("document__title", "user__email")
    readonly_fields = ("id", "metadata", "ip_address", "created_at")