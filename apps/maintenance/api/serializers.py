from rest_framework import serializers
from ..models import (
    MaintenanceCategory, MaintenanceRequest, MaintenanceAssignment,
    MaintenanceUpdate, MaintenanceMedia, MaintenanceInspection
)

class CategorySerializer(serializers.ModelSerializer):
    name_display = serializers.CharField(source="name", read_only=True)
    
    class Meta:
        model = MaintenanceCategory
        # ✅ FIXED: Added 'name_display' to fields to resolve AssertionError
        fields = ["id", "code", "name", "name_display", "default_sla_hours", "is_active"]
        read_only_fields = ["id", "is_active", "name_display"]

class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceMedia
        fields = ["id", "media_type", "file_url", "caption", "is_before_after", "created_at"]
        read_only_fields = ["id", "created_at"]

class AssignmentSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source="assigned_to.get_full_name", read_only=True, allow_null=True)
    
    class Meta:
        model = MaintenanceAssignment
        fields = ["id", "assigned_to", "assigned_to_name", "role_type", "status", "assigned_at", "acknowledged_at", "notes"]
        read_only_fields = ["id", "status", "assigned_at", "acknowledged_at"]

class UpdateSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source="updated_by.get_full_name", read_only=True, allow_null=True)
    
    class Meta:
        model = MaintenanceUpdate
        fields = ["id", "comment", "previous_status", "new_status", "updated_by_name", "created_at"]
        read_only_fields = ["id", "previous_status", "new_status", "updated_by_name", "created_at"]

class RequestDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    # Note: Ensure 'current_assignment' is a valid property or related_name on MaintenanceRequest
    assignment = AssignmentSerializer(source="current_assignment", read_only=True, allow_null=True)
    media = MediaSerializer(many=True, read_only=True)
    updates = UpdateSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)

    class Meta:
        model = MaintenanceRequest
        fields = [
            "id", "title", "description", "category", "priority", "priority_display",
            "status", "status_display", "sla_due_at", "assignment",
            "media", "updates", "resolved_at", "closed_at", "created_at"
        ]
        read_only_fields = ["id", "status", "sla_due_at", "resolved_at", "closed_at", "created_at"]

class RequestCreateSerializer(serializers.Serializer):
    unit_id = serializers.UUIDField(help_text="Target unit for the maintenance request")
    category_id = serializers.UUIDField(help_text="Maintenance category ID")
    title = serializers.CharField(max_length=200, help_text="Brief issue title")
    description = serializers.CharField(required=True, help_text="Detailed description of the reported issue")
    priority = serializers.ChoiceField(
        choices=["low", "medium", "high", "emergency"],
        required=False,
        default="medium",
        help_text="Issue severity level"
    )

class InspectionSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(source="inspector.get_full_name", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = MaintenanceInspection
        fields = [
            "id", "property", "unit", "inspector", "inspector_name", 
            "inspection_date", "findings", "status", "status_display", "created_at"
        ]
        read_only_fields = ["id", "status", "inspector", "created_at"]

class InspectionCreateSerializer(serializers.Serializer):
    property_id = serializers.UUIDField(required=True, help_text="Target property ID")
    unit_id = serializers.UUIDField(required=False, allow_null=True, help_text="Target unit ID (optional)")
    inspection_date = serializers.DateField(required=True, help_text="Scheduled or actual inspection date")
    findings = serializers.CharField(required=True, help_text="Detailed inspection observations")