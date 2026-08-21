import hashlib
import json
from datetime import timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, models, transaction
from django.utils import timezone
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .exceptions import Conflict, MissingIdempotencyKey
from .models import AuditEvent, IdempotencyRecord
from .permissions import active_roles


def request_uuid(request):
    return getattr(request, "request_id")


def json_safe(value):
    """Return a deterministic JSON value without serializing model display text."""
    if isinstance(value, models.Model):
        return str(value.pk)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def safe_model_projection(instance, fields, many_to_many=()):
    """Build an explicitly allowlisted audit snapshot without model string values."""
    projection = {field: json_safe(getattr(instance, field)) for field in fields}
    for field in many_to_many:
        projection[field] = sorted(str(pk) for pk in getattr(instance, field).values_list("pk", flat=True))
    return projection


def audit(request, event_type, subject, action, changes=None, reason=""):
    roles = sorted(active_roles(request.user)) if getattr(request.user, "is_authenticated", False) else []
    return AuditEvent.objects.create(
        event_type=event_type,
        actor=request.user if getattr(request.user, "is_authenticated", False) else None,
        actor_role=roles[0] if roles else "",
        subject_type=subject.__class__.__name__ if subject else "system",
        subject_id=getattr(subject, "pk", None),
        action=action,
        changes=json_safe(changes or {}),
        reason=reason,
        request_id=request_uuid(request),
    )


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _request_digest(request):
    canonical = json.dumps(request.data, sort_keys=True, separators=(",", ":"), default=str).encode()
    return _digest(request.method.encode() + b"\n" + request.path.encode() + b"\n" + canonical)


def idempotent(request, scope, operation):
    key = request.headers.get("Idempotency-Key", "").strip()
    if len(key) < 8 or len(key) > 128:
        raise MissingIdempotencyKey()
    key_digest = _digest(key.encode())
    payload_digest = _request_digest(request)
    with transaction.atomic():
        # The unique constraint is the final guard. This transaction-scoped lock
        # also makes concurrent first use of the same key replay predictably.
        lock_bytes = hashlib.sha256(f"{request.user.pk}:{scope}:{key_digest}".encode()).digest()[:8]
        lock_id = int.from_bytes(lock_bytes, byteorder="big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
        existing = IdempotencyRecord.objects.select_for_update().filter(actor=request.user, scope=scope, key_digest=key_digest).first()
        if existing:
            if existing.request_digest != payload_digest:
                raise Conflict("This idempotency key was already used with a different request.", code="idempotency_key_reused")
            if existing.state == IdempotencyRecord.State.COMPLETED:
                response = Response(existing.response_body, status=existing.response_status)
                response["Idempotency-Replayed"] = "true"
                return response
            raise Conflict("The original request is still being processed.", code="idempotency_in_progress")
        record = IdempotencyRecord.objects.create(
            actor=request.user,
            scope=scope,
            key_digest=key_digest,
            request_digest=payload_digest,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        result = operation()
        if isinstance(result, Response):
            response = result
        else:
            body, response_status = result
            response = Response(body, status=response_status)
        try:
            safe_body = json.loads(JSONRenderer().render(response.data))
        except (TypeError, ValueError):
            raise RuntimeError("Idempotent responses must be JSON serializable")
        record.state = IdempotencyRecord.State.COMPLETED
        record.response_status = response.status_code
        record.response_body = safe_body
        record.save(update_fields=["state", "response_status", "response_body", "updated_at"])
        return response
