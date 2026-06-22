from rest_framework import serializers
from ..models import (
    DocumentType, DocumentTemplate, Document, DocumentVersion,
    DocumentAttachment, DocumentAuditLog, GeneratedDocument, DocumentStatus
)

class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ["id", "code", "name", "requires_signature", "is_active"]
        read_only_fields = ["id", "is_active"]

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = ["id", "name", "document_type", "variables", "is_default", "is_active"]
        read_only_fields = ["id", "is_active", "variables"]

class DocumentVersionSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.get_full_name", read_only=True, allow_null=True)
    class Meta:
        model = DocumentVersion
        fields = ["id", "version_number", "file_url", "changed_by_name", "change_reason", "created_at"]
        read_only_fields = ["id", "created_at"]

class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True, allow_null=True)
    class Meta:
        model = DocumentAttachment
        fields = ["id", "file_url", "file_type", "caption", "uploaded_by_name", "created_at"]
        read_only_fields = ["id", "created_at"]

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, allow_null=True)
    class Meta:
        model = DocumentAuditLog
        fields = ["id", "action", "user_email", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]

class GeneratedDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedDocument
        fields = ["id", "status", "generation_variables", "checksum", "file_size", "page_count", "generated_at"]
        read_only_fields = ["id", "status", "checksum", "generated_at"]

class DocumentDetailSerializer(serializers.ModelSerializer):
    document_type = DocumentTypeSerializer(read_only=True)
    template = DocumentTemplateSerializer(read_only=True)
    versions = DocumentVersionSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    audit_trail = AuditLogSerializer(many=True, read_only=True)
    generated_record = GeneratedDocumentSerializer(read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.get_full_name", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id", "title", "document_type", "template", "file_url", "status", "status_display",
            "assigned_to", "assigned_to_name", "expires_at", "metadata",
            "versions", "attachments", "audit_trail", "generated_record",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "title": {"help_text": "Display name of the document instance"},
            "metadata": {"help_text": "JSON payload for document-specific context"},
            "file_url": {"help_text": "Storage path or presigned URL for the file"},
            "expires_at": {"help_text": "Date after which the document is no longer valid"}
        }

class DocumentCreateSerializer(serializers.Serializer):
    document_type_id = serializers.UUIDField(help_text="Target document type ID")
    title = serializers.CharField(max_length=200, help_text="Document title")
    file_url = serializers.URLField(help_text="Path to the uploaded document file")
    tenancy_id = serializers.UUIDField(required=False, help_text="Associated tenancy reference")
    expires_at = serializers.DateTimeField(required=False, help_text="Expiration timestamp")

class GenerateDocumentSerializer(serializers.Serializer):
    document_type_code = serializers.CharField(max_length=50, help_text="Code of the document template to use")
    entity_ref = serializers.JSONField(help_text="Context data (e.g., {'tenancy_id': '...'})")
    variables = serializers.JSONField(help_text="Key-value pairs for template variable injection")
    title = serializers.CharField(max_length=200, required=False, help_text="Custom title for generated file")
    expires_at = serializers.DateTimeField(required=False, help_text="Validity expiration timestamp")

class SignatureActionSerializer(serializers.Serializer):
    signature_metadata = serializers.JSONField(required=False, help_text="Contextual data (IP, Device, e-Sign hash)")
    rejection_reason = serializers.CharField(max_length=500, required=False, help_text="Reason for document rejection")