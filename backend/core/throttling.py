import hashlib
import time
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

from .models import RateLimitBucket


class DatabaseScopedRateThrottle(BaseThrottle):
    """A process-independent fixed-window throttle backed by PostgreSQL."""

    scope = None

    def _rate(self, view):
        scope = getattr(view, "throttle_scope", self.scope)
        rate = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}).get(scope)
        if not scope or not rate:
            return None
        count, period = rate.split("/", 1)
        requests = int(count)
        seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[period[0].lower()]
        return scope, requests, seconds

    def _identity(self, request):
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.pk}"
        address = request.META.get("REMOTE_ADDR", "unknown")
        if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            if forwarded:
                address = forwarded.split(",", 1)[0].strip()
        return f"ip:{address[:80]}"

    def allow_request(self, request, view):
        parsed = self._rate(view)
        if not parsed:
            return True
        scope, limit, duration = parsed
        now_epoch = int(time.time())
        window = now_epoch // duration
        raw_key = f"{scope}:{duration}:{window}:{self._identity(request)}"
        key_digest = hashlib.sha256(raw_key.encode()).hexdigest()
        expires_at = timezone.now() + timedelta(seconds=duration - (now_epoch % duration) + 1)
        advisory_id = int.from_bytes(bytes.fromhex(key_digest[:16]), byteorder="big", signed=True)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [advisory_id])
            bucket, _ = RateLimitBucket.objects.select_for_update().get_or_create(
                key_digest=key_digest,
                defaults={"scope": scope, "request_count": 0, "expires_at": expires_at},
            )
            bucket.request_count += 1
            bucket.save(update_fields=["request_count"])
        self.wait_seconds = max(1, duration - (now_epoch % duration))
        return bucket.request_count <= limit

    def wait(self):
        return self.wait_seconds
