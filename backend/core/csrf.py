from django.http import JsonResponse


def csrf_failure(request, reason=""):
    return JsonResponse(
        {
            "status": 403,
            "code": "csrf_failed",
            "title": "Permission denied",
            "detail": "The security token is missing or invalid. Refresh the page and try again.",
            "field_errors": {},
            "request_id": str(getattr(request, "request_id", "")),
        },
        status=403,
    )
