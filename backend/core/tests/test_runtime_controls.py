import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AccountToken, RoleAssignment, User
from accounts.services import digest_token
from core.models import IdempotencyRecord, RateLimitBucket


class RuntimeControlTests(TestCase):
    def user(self):
        user = User.objects.create_user(
            "runtime@example.test",
            "RuntimeControls!2026",
            display_name="Runtime Patient",
            email_verified_at=timezone.now(),
        )
        RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.PATIENT)
        return user

    def test_health_and_api_cache_contract_disclose_no_version(self):
        response = APIClient().get("/api/v1/health/live/")
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["Pragma"], "no-cache")

    def test_idle_session_is_rejected_server_side(self):
        user = self.user()
        client = APIClient()
        client.force_login(user)
        session = client.session
        now = int(timezone.now().timestamp())
        session["session_created_at"] = now - 120
        session["session_last_activity_at"] = now - 61
        session.save()
        with override_settings(SESSION_IDLE_TIMEOUT_SECONDS=60, SESSION_ABSOLUTE_TIMEOUT_SECONDS=300):
            response = client.get("/api/v1/auth/session/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "session_expired")

    def test_anonymous_pending_mfa_challenge_has_a_short_server_limit(self):
        client = APIClient()
        session = client.session
        session["pending_mfa_user_id"] = str(uuid.uuid4())
        session["mfa_challenge_started_at"] = int(timezone.now().timestamp()) - 601
        session.save()
        response = client.get("/api/v1/auth/session/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "mfa_challenge_expired")

    def test_pending_mfa_replacement_expires_and_ends_the_staff_session(self):
        user = self.user()
        RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.ADMINISTRATOR)
        client = APIClient()
        client.force_login(user)
        session = client.session
        session["mfa_verified"] = True
        session["mfa_replacement_device_id"] = str(uuid.uuid4())
        session["mfa_replacement_started_at"] = int(timezone.now().timestamp()) - 601
        session.save()
        response = client.get("/api/v1/auth/session/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "mfa_challenge_expired")
        self.assertFalse(client.session.get("_auth_user_id"))

    def test_database_public_throttle_is_shared_and_returns_retry_after(self):
        configured = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {"auth": "60/min", "public": "2/min", "write": "120/min"},
        }
        client = APIClient()
        with override_settings(REST_FRAMEWORK=configured):
            self.assertEqual(client.get("/api/v1/public/doctors/").status_code, 200)
            self.assertEqual(client.get("/api/v1/public/doctors/").status_code, 200)
            blocked = client.get("/api/v1/public/doctors/")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked)
        self.assertEqual(RateLimitBucket.objects.count(), 1)

    def test_cleanup_command_removes_only_expired_control_state(self):
        user = self.user()
        expired = timezone.now() - timedelta(minutes=1)
        RateLimitBucket.objects.create(
            key_digest="a" * 64,
            scope="test",
            request_count=1,
            expires_at=expired,
        )
        IdempotencyRecord.objects.create(
            actor=user,
            scope="test",
            key_digest="b" * 64,
            request_digest="c" * 64,
            expires_at=expired,
        )
        AccountToken.objects.create(
            user=user,
            purpose=AccountToken.Purpose.RESET_PASSWORD,
            token_digest=digest_token("expired-token"),
            expires_at=expired,
        )
        AccountToken.objects.create(
            user=user,
            purpose=AccountToken.Purpose.VERIFY_EMAIL,
            token_digest=digest_token("used-token"),
            expires_at=timezone.now() + timedelta(hours=1),
            used_at=timezone.now(),
        )
        session = SessionStore()
        session["synthetic"] = True
        session.set_expiry(-1)
        session.save()
        call_command("cleanup_expired_state", verbosity=0)
        self.assertFalse(RateLimitBucket.objects.exists())
        self.assertFalse(IdempotencyRecord.objects.exists())
        self.assertFalse(AccountToken.objects.exists())
        self.assertFalse(SessionStore(session_key=session.session_key).exists(session.session_key))
