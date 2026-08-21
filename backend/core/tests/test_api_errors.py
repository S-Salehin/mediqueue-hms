import json

from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.test import APIClient
from rest_framework.views import APIView

from core.logging import JSONFormatter


class SyntheticFailureView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        raise RuntimeError("Synthetic Patient Secret 01700000000")


urlpatterns = [path("api/v1/test/unhandled/", SyntheticFailureView.as_view())]


class APIErrorEnvelopeTests(TestCase):
    fields = {"status", "code", "title", "detail", "field_errors", "request_id"}

    def assert_envelope(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertEqual(set(response.json()), self.fields)
        self.assertTrue(response.json()["request_id"])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_unknown_api_route_is_json_even_with_debug_enabled(self):
        self.assert_envelope(APIClient().get("/api/v1/not-a-real-route/"), 404)

    def test_malformed_json_uses_stable_envelope(self):
        response = APIClient().generic(
            "POST",
            "/api/v1/auth/login/",
            b'{"email":',
            content_type="application/json",
        )
        self.assert_envelope(response, 400)

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=32)
    def test_oversized_body_uses_stable_envelope(self):
        response = APIClient().generic(
            "POST",
            "/api/v1/auth/login/",
            json.dumps({"email": "patient@example.test", "password": "x" * 200}),
            content_type="application/json",
        )
        self.assert_envelope(response, 413)

    @override_settings(ROOT_URLCONF=__name__, DEBUG=False)
    def test_unhandled_api_error_is_generic_and_logged_without_message(self):
        with self.assertLogs("api.errors", level="ERROR") as captured:
            response = APIClient().get("/api/v1/test/unhandled/")
        self.assert_envelope(response, 500)
        self.assertEqual(response.json()["code"], "internal_error")
        joined = "\n".join(captured.output)
        self.assertIn("unhandled_api_exception", joined)
        self.assertEqual(captured.records[0].exception_class, "RuntimeError")
        self.assertEqual(captured.records[0].view, "SyntheticFailureView")
        self.assertNotIn("Synthetic Patient Secret", joined)
        self.assertNotIn("01700000000", joined)

    def test_json_formatter_exposes_only_allowlisted_error_context(self):
        import logging

        record = logging.LogRecord(
            "api.errors",
            logging.ERROR,
            __file__,
            1,
            "unhandled_api_exception",
            (),
            None,
        )
        record.event = "unhandled_api_exception"
        record.exception_class = "RuntimeError"
        record.view = "SyntheticFailureView"
        record.request_id = "test-request-id"
        record.patient_name = "Must Not Appear"
        payload = json.loads(JSONFormatter().format(record))
        self.assertEqual(
            set(payload),
            {"timestamp", "level", "logger", "message", "request_id", "event", "exception_class", "view"},
        )
        self.assertNotIn("Must Not Appear", json.dumps(payload))
