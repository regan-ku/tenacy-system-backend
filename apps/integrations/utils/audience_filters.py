from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from typing import Dict, Any

def build_campaign_audience(filters: Dict[str, Any]) -> Q:
    """
    Builds Django Q object for campaign audience targeting.
    Supports role, location, tenancy status, arrears, and engagement filters.
    """
    q = Q()

    if filters.get("role"):
        q &= Q(role=filters["role"])
    if filters.get("city"):
        q &= Q(profile__city__iexact=filters["city"])
    if filters.get("tenancy_status"):
        q &= Q(tenancies__status=filters["tenancy_status"])
    if filters.get("has_arrears"):
        q &= Q(tenant_balance__gt=0)
    if filters.get("overdue_days__gte"):
        cutoff = timezone.now() - timedelta(days=int(filters["overdue_days__gte"]))
        q &= Q(last_payment_date__lt=cutoff)
    if filters.get("inactive_days__gte"):
        cutoff = timezone.now() - timedelta(days=int(filters["inactive_days__gte"]))
        q &= Q(last_login__lt=cutoff)

    return q

def validate_audience_size(count: int, max_limit: int = 10000) -> Dict[str, Any]:
    """Prevents accidental massive broadcasts by enforcing safe limits"""
    return {
        "is_valid": count <= max_limit,
        "count": count,
        "limit": max_limit,
        "message": f"Audience size: {count} exceeds limit of {max_limit}" if count > max_limit else "Valid audience size"
    }