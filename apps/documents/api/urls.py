from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentTypeViewSet, DocumentTemplateViewSet, DocumentViewSet

router = DefaultRouter()
router.register(r"types", DocumentTypeViewSet, basename="document-type")
router.register(r"templates", DocumentTemplateViewSet, basename="document-template")
router.register(r"documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("", include(router.urls)),
    # Explicit action routes for clarity & frontend integration
    path("documents/<uuid:id>/download/", DocumentViewSet.as_view({"get": "download"}), name="document-download"),
    path("documents/<uuid:id>/request-signature/", DocumentViewSet.as_view({"post": "request_signature"}), name="doc-request-signature"),
    path("documents/<uuid:id>/sign/", DocumentViewSet.as_view({"post": "sign"}), name="doc-sign"),
    path("documents/<uuid:id>/reject/", DocumentViewSet.as_view({"post": "reject"}), name="doc-reject"),
    path("documents/<uuid:id>/create-version/", DocumentViewSet.as_view({"post": "create_version"}), name="doc-create-version"),
    path("documents/<uuid:id>/audit-trail/", DocumentViewSet.as_view({"get": "audit_trail"}), name="doc-audit-trail"),
]