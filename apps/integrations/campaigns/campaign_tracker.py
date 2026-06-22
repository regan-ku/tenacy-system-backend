from django.db import transaction
from ..models import Campaign

class CampaignTracker:
    @staticmethod
    def increment_sent(campaign_id: str, count: int = 1):
        with transaction.atomic():
            Campaign.objects.filter(id=campaign_id).update(
                total_sent=Campaign.objects.get(id=campaign_id).total_sent + count
            )

    @staticmethod
    def increment_delivered(campaign_id: str, count: int = 1):
        with transaction.atomic():
            Campaign.objects.filter(id=campaign_id).update(
                total_delivered=Campaign.objects.get(id=campaign_id).total_delivered + count
            )

    @staticmethod
    def mark_completed(campaign_id: str):
        from ..models import CampaignStatus
        Campaign.objects.filter(id=campaign_id).update(status=CampaignStatus.COMPLETED)

    @staticmethod
    def mark_failed(campaign_id: str, error_reason: str = "Unknown"):
        from ..models import CampaignStatus
        Campaign.objects.filter(id=campaign_id).update(status=CampaignStatus.FAILED)