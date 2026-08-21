from django.contrib.sessions.models import Session
from django.db.models import Q
from django.utils import timezone

from accounts.models import AccountToken

from .models import IdempotencyRecord, RateLimitBucket


def cleanup_expired_control_records(now=None):
    """Remove expired technical control data, never business or audit history."""
    now = now or timezone.now()
    counts = {}
    counts["rate_limit_buckets"] = RateLimitBucket.objects.filter(expires_at__lt=now).delete()[0]
    counts["idempotency_records"] = IdempotencyRecord.objects.filter(expires_at__lt=now).delete()[0]
    counts["account_tokens"] = AccountToken.objects.filter(
        Q(expires_at__lt=now) | Q(used_at__isnull=False)
    ).delete()[0]
    counts["sessions"] = Session.objects.filter(expire_date__lt=now).delete()[0]
    return counts
