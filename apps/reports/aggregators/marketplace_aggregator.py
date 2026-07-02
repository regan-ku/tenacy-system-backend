from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.apps import apps

from apps.reports.utils.filters import ReportFilterUtils
from apps.reports.utils.calculations import CalculationUtils

class MarketplaceAggregator:
    """
    Computes marketplace and lead-generation KPIs for dashboards and reports.
    """

    @staticmethod
    def get_marketplace_summary(user, days=30):
        """
        Returns total listing views, inquiries (saved listings/applications), 
        and conversion rates scoped to the user's properties.
        """
        ListingView = apps.get_model('marketplace', 'ListingView')
        SavedListing = apps.get_model('marketplace', 'SavedListing')
        Property = apps.get_model('properties', 'Property')
        Application = apps.get_model('applications', 'Application')

        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return {
                "period_days": days,
                "total_views": 0,
                "total_saved": 0,
                "total_applications": 0,
                "conversion_rate": 0.0
            }

        cutoff_date = timezone.now() - timedelta(days=days)

        total_views = ListingView.objects.filter(
            listing__property_id__in=property_ids,
            viewed_at__gte=cutoff_date
        ).count()

        total_saved = SavedListing.objects.filter(
            listing__property_id__in=property_ids,
            created_at__gte=cutoff_date
        ).count()

        total_applications = Application.objects.filter(
            property_id__in=property_ids,
            created_at__gte=cutoff_date,
            status='approved' 
        ).count()

        conversion_rate = CalculationUtils.calculate_percentage(total_applications, total_views)

        return {
            "period_days": days,
            "total_views": total_views,
            "total_saved": total_saved,
            "total_applications": total_applications,
            "conversion_rate": conversion_rate
        }

    @staticmethod
    def get_top_performing_listings(user, limit=5):
        """
        Returns the top-performing listings based on view count for charting/tables.
        """
        Listing = apps.get_model('marketplace', 'Listing')
        Property = apps.get_model('properties', 'Property')

        accessible_properties = ReportFilterUtils.scope_properties_by_user(user, Property.objects.all())
        property_ids = accessible_properties.values_list('id', flat=True)

        if not property_ids:
            return []

        top_listings = Listing.objects.filter(
            property_id__in=property_ids,
            status='active'
        ).annotate(
            view_count=Count('listingview') # Django automatically resolves this reverse relation
        ).order_by('-view_count')[:limit]

        return [
            {
                "listing_id": listing.id,
                "property_title": listing.property.title,
                "unit_code": listing.unit.unit_code if listing.unit else "Property-wide",
                "views": listing.view_count
            }
            for listing in top_listings
        ]