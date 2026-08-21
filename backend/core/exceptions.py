import logging

from django.core.exceptions import RequestDataTooBig
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("api.errors")


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The requested change conflicts with the current state."
    default_code = "conflict"


class MissingIdempotencyKey(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An Idempotency-Key header is required."
    default_code = "idempotency_key_required"


class AccountTemporarilyLocked(exceptions.APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many authentication attempts. Wait before trying again."
    default_code = "account_temporarily_locked"


class PayloadTooLarge(exceptions.APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The request body is too large."
    default_code = "request_too_large"


def _field_errors(data):
    if not isinstance(data, dict):
        return {}
    result = {}
    for key, value in data.items():
        if key in {"detail", "status"}:
            continue
        if key == "code" and "detail" in data and not isinstance(value, (list, tuple, dict)):
            continue
        if isinstance(value, (list, tuple)):
            result[key] = [str(item) for item in value]
        elif isinstance(value, dict):
            result[key] = value
        else:
            result[key] = [str(value)]
    return result


def api_exception_handler(exc, context):
    if isinstance(exc, RequestDataTooBig):
        exc = PayloadTooLarge()
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(getattr(exc, "message_dict", exc.messages))
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = str(getattr(request, "request_id", ""))
    if response is None:
        view = context.get("view")
        logger.error(
            "unhandled_api_exception",
            extra={
                "event": "unhandled_api_exception",
                "exception_class": exc.__class__.__name__,
                "request_id": request_id,
                "view": view.__class__.__name__ if view else "unknown",
            },
        )
        return Response(
            {
                "status": 500,
                "code": "internal_error",
                "title": "Unexpected server error",
                "detail": "The request could not be completed. Use the request identifier when contacting support.",
                "field_errors": {},
                "request_id": request_id,
            },
            status=500,
        )
    detail = response.data.get("detail") if isinstance(response.data, dict) else response.data
    code = getattr(exc, "default_code", "error")
    if hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, str):
            code = codes
        elif isinstance(codes, dict) and "detail" in codes and isinstance(codes["detail"], str):
            code = codes["detail"]
    titles = {
        400: "Request could not be accepted",
        401: "Authentication required",
        403: "Permission denied",
        404: "Resource not found",
        405: "Method not allowed",
        409: "Request conflicts with current state",
        413: "Request body is too large",
        415: "Unsupported content type",
        429: "Too many requests",
    }
    response.data = {
        "status": response.status_code,
        "code": str(code),
        "title": titles.get(response.status_code, "Request failed"),
        "detail": str(detail or titles.get(response.status_code, "Request failed")),
        "field_errors": _field_errors(response.data) if response.status_code == 400 else {},
        "request_id": request_id,
    }
    return response
