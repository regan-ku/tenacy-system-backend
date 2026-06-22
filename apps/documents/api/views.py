from rest_framework import viewsets, mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import (
    DocumentTypeSerializer, DocumentTemplateSerializer, DocumentDetailSerializer,
    DocumentCreateSerializer, GenerateDocumentSerializer, SignatureActionSerializer,
    DocumentVersionSerializer, AttachmentSerializer, AuditLogSerializer
)
from ..models import (
    DocumentType, DocumentTemplate, Document, DocumentVersion, DocumentAttachment
)
from ..permissions.document_permissions import (
    IsDocumentStakeholder, CanSignDocument, CanManageVersions,
    CanGenerateDocuments, CanViewAuditLogs
)
from ..services.document_service import DocumentService
from ..services.versioning_service import VersioningService
from ..services.signing_service import SigningService
from ..services.storage_service import StorageService
from ..tasks.document_generation_tasks import generate_document_task
import logging

logger = logging.getLogger(__name__)

# ================= LOOKUPS =================
class DocumentTypeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = DocumentTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DocumentType.objects.none()
        return DocumentType.objects.filter(is_active=True)

class DocumentTemplateViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DocumentTemplate.objects.none()
        return DocumentTemplate.objects.filter(is_active=True)

# ================= CORE DOCUMENTS =================
class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsDocumentStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        qs = Document.objects.select_related(
            "document_type", "template", "uploaded_by", "assigned_to"
        ).prefetch_related("versions", "attachments", "audit_trail", "generated_record")
        return qs.order_by("-created_at")

    # ✅ FIXED: Explicit operation_id
    @extend_schema(
        operation_id="documents_generate_create",
        request=GenerateDocumentSerializer, 
        responses={202: OpenApiResponse(description="Generation task queued")}
    )
    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanGenerateDocuments])
    def generate(self, request):
        serializer = GenerateDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        task = generate_document_task.delay(
            document_type_code=data["document_type_code"],
            entity_ref=data["entity_ref"],
            variables=data["variables"],
            title=data.get("title"),
            user_id=str(request.user.id),
            expires_at_iso=data.get("expires_at").isoformat() if data.get("expires_at") else None
        )
        return Response({"status": "queued", "task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    # ✅ FIXED: Explicit operation_id
    @extend_schema(
        operation_id="documents_download_retrieve",
        responses={200: OpenApiResponse(description="Secure time-bound download URL")}
    )
    @action(detail=True, methods=["get"])
    def download(self, request, id=None):
        doc = self.get_object()
        if not doc.file_url:
            return Response({"error": "Document file not available"}, status=status.HTTP_404_NOT_FOUND)
        signed_url = StorageService.generate_signed_url(doc.file_url, expires_hours=2)
        return Response({"download_url": signed_url, "expires_in_seconds": 7200})

    # ✅ FIXED: Explicit url_path and operation_id to resolve collision
    @extend_schema(
        operation_id="documents_request_signature_create",
        responses={200: OpenApiResponse(description="Signature request sent")}
    )
    @action(detail=True, methods=["post"], url_path="request-signature", permission_classes=[permissions.IsAuthenticated, CanManageVersions])
    def request_signature(self, request, id=None):
        doc = self.get_object()
        signer_id = request.data.get("signer_id")
        if not signer_id:
            return Response({"error": "signer_id required"}, status=status.HTTP_400_BAD_REQUEST)
        SigningService.request_signature(str(doc.id), signer_id)
        return Response({"status": "signature_requested"})

    # ✅ FIXED: Explicit operation_id
    @extend_schema(
        operation_id="documents_sign_create",
        request=SignatureActionSerializer,
        responses={200: OpenApiResponse(description="Document signed")}
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanSignDocument])
    def sign(self, request, id=None):
        doc = self.get_object()
        serializer = SignatureActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        SigningService.mark_signed(str(doc.id), str(request.user.id), serializer.validated_data.get("signature_metadata"))
        return Response({"status": "signed"})

    # ✅ FIXED: Explicit operation_id
    @extend_schema(
        operation_id="documents_reject_create",
        request=SignatureActionSerializer,
        responses={200: OpenApiResponse(description="Document rejected")}
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanSignDocument])
    def reject(self, request, id=None):
        doc = self.get_object()
        serializer = SignatureActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("rejection_reason", "No reason provided")
        SigningService.reject_document(str(doc.id), str(request.user.id), reason)
        return Response({"status": "rejected"})

    # ✅ FIXED: Explicit url_path and operation_id to resolve collision
    @extend_schema(
        operation_id="documents_create_version_create",
        responses={200: OpenApiResponse(description="New version created")}
    )
    @action(detail=True, methods=["post"], url_path="create-version", permission_classes=[permissions.IsAuthenticated, CanManageVersions])
    def create_version(self, request, id=None):
        doc = self.get_object()
        file_url = request.data.get("file_url")
        change_reason = request.data.get("change_reason", "Manual version update")
        if not file_url:
            return Response({"error": "file_url required"}, status=status.HTTP_400_BAD_REQUEST)
        VersioningService.create_new_version(str(doc.id), file_url, request.user, change_reason)
        return Response({"status": "version_created"})

    # ✅ FIXED: Explicit url_path and operation_id to resolve collision
    @extend_schema(
        operation_id="documents_audit_trail_retrieve",
        responses={200: AuditLogSerializer(many=True)}
    )
    @action(detail=True, methods=["get"], url_path="audit-trail", permission_classes=[permissions.IsAuthenticated, CanViewAuditLogs])
    def audit_trail(self, request, id=None):
        doc = self.get_object()
        logs = doc.audit_trail.all()[:50]
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)