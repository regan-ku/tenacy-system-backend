from rest_framework import serializers
from ..models import Message, Notification, Campaign, CampaignAudience, MessageTemplate

class MessageSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    message_type_display = serializers.CharField(source="get_message_type_display", read_only=True)
    
    class Meta:
        model = Message
        fields = [
            "id", "recipient", "channel", "message_type", "message_type_display",
            "content", "status", "status_display", "sent_at", "delivered_at", "created_at"
        ]
        read_only_fields = ["id", "status", "sent_at", "delivered_at", "created_at"]

class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "type", "type_display", "is_read", "action_link", "created_at"]
        read_only_fields = ["id", "created_at"]

class NotificationMarkReadSerializer(serializers.Serializer):
    is_read = serializers.BooleanField(default=True)

class CampaignAudienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignAudience
        fields = ["id", "campaign", "audience_type", "filter_criteria", "estimated_count", "created_at"]
        read_only_fields = ["id", "estimated_count", "created_at", "campaign"]

class CampaignSerializer(serializers.ModelSerializer):
    audiences = CampaignAudienceSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            "id", "title", "template", "channel", "channel_display", "status", 
            "status_display", "scheduled_at", "total_sent", "total_delivered", 
            "metrics", "audiences", "created_at"
        ]
        read_only_fields = ["id", "status", "total_sent", "total_delivered", "created_at"]

class CampaignCreateSerializer(serializers.ModelSerializer):
    audiences = CampaignAudienceSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Campaign
        fields = ["id", "title", "template", "channel", "scheduled_at", "audiences"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        audiences_data = validated_data.pop("audiences", [])
        campaign = Campaign.objects.create(**validated_data)
        for aud in audiences_data:
            CampaignAudience.objects.create(campaign=campaign, **aud)
        return campaign

class MessageTemplateSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    
    class Meta:
        model = MessageTemplate
        fields = ["id", "name", "channel", "channel_display", "subject", "body", "required_variables", "is_active", "updated_at"]
        read_only_fields = ["id", "updated_at"]