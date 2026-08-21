import json
import re
import uuid

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone

REQUEST_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        try:
            request_id = uuid.UUID(supplied) if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4()
        except ValueError:
            request_id = uuid.uuid4()
        request.request_id = request_id
        response = self.get_response(request)
        if request.path.startswith("/api/") and response.status_code >= 400:
            is_json = response.get("Content-Type", "").startswith("application/json")
            try:
                body = json.loads(response.content.decode("utf-8")) if is_json and response.content else {}
            except (ValueError, UnicodeDecodeError):
                body = {}
            if not isinstance(body, dict) or not {"status", "code", "title", "detail", "field_errors", "request_id"}.issubset(body):
                generic_codes = {
                    400: "invalid_request",
                    401: "not_authenticated",
                    403: "permission_denied",
                    404: "not_found",
                    405: "method_not_allowed",
                    413: "request_too_large",
                    429: "throttled",
                    500: "internal_error",
                    503: "service_unavailable",
                }
                generic_details = {
                    400: "The request could not be accepted.",
                    404: "The requested API resource was not found.",
                    413: "The request body is too large.",
                    500: "The request could not be completed. Use the request identifier when contacting support.",
                }
                detail = body.get("detail") if is_json and isinstance(body, dict) else None
                code = body.get("code") if is_json and isinstance(body, dict) else None
                titles = {
                    400: "Request could not be accepted",
                    401: "Authentication required",
                    403: "Permission denied",
                    404: "Resource not found",
                    409: "Request conflicts with current state",
                    413: "Request body is too large",
                    429: "Too many requests",
                    503: "Service unavailable",
                }
                replacement = JsonResponse(
                    {
                        "status": response.status_code,
                        "code": code or generic_codes.get(response.status_code, "request_failed"),
                        "title": titles.get(response.status_code, "Request failed"),
                        "detail": str(detail or generic_details.get(response.status_code, "The request could not be completed.")),
                        "field_errors": body.get("field_errors", {}) if is_json and isinstance(body, dict) else {},
                        "request_id": str(request_id),
                    },
                    status=response.status_code,
                )
                for header, value in response.items():
                    if header.lower() != "content-type":
                        replacement[header] = value
                response = replacement
        response["X-Request-ID"] = str(request_id)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "private, no-store"
            response["Pragma"] = "no-cache"
        return response


class SessionLifetimeMiddleware:
    """Enforce server-side idle and absolute limits for authenticated sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        now = int(timezone.now().timestamp())
        challenge_started = (
            request.session.get("mfa_challenge_started_at")
            or request.session.get("mfa_enrollment_started_at")
            or request.session.get("mfa_replacement_started_at")
        )
        if challenge_started and now - int(challenge_started) >= settings.MFA_CHALLENGE_TIMEOUT_SECONDS:
            request.session.flush()
            return JsonResponse(
                {
                    "status": 401,
                    "code": "mfa_challenge_expired",
                    "title": "Authentication challenge expired",
                    "detail": "Start the sign in or invitation flow again.",
                    "field_errors": {},
                    "request_id": str(request.request_id),
                },
                status=401,
            )
        if request.user.is_authenticated:
            created = int(request.session.get("session_created_at", now))
            activity = int(request.session.get("session_last_activity_at", now))
            absolute_age = now - created
            idle_age = now - activity
            if absolute_age >= settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS or idle_age >= settings.SESSION_IDLE_TIMEOUT_SECONDS:
                logout(request)
                return JsonResponse(
                    {
                        "status": 401,
                        "code": "session_expired",
                        "title": "Session expired",
                        "detail": "Sign in again to continue.",
                        "field_errors": {},
                        "request_id": str(request.request_id),
                    },
                    status=401,
                )
            if "session_created_at" not in request.session:
                request.session["session_created_at"] = created
            if now - activity >= 60 or "session_last_activity_at" not in request.session:
                request.session["session_last_activity_at"] = now
        return self.get_response(request)
