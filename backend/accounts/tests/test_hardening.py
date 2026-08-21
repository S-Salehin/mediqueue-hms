import uuid
from unittest.mock import patch

import pyotp
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AccountToken, RoleAssignment, StaffMFADevice, User
from accounts.services import (
    confirm_mfa_replacement,
    generate_recovery_codes,
    issue_account_token,
    start_mfa_replacement,
    verify_mfa_code,
)
from core.exceptions import Conflict


class IdentityHardeningTests(TestCase):
    def staff(self):
        user = User.objects.create_user(
            "hardening-staff@example.test",
            "HardeningStaff!2026",
            display_name="Hardening Staff",
            email_verified_at=timezone.now(),
            is_staff=True,
        )
        RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.ADMINISTRATOR)
        return user

    def device(self, user):
        secret = pyotp.random_base32()
        device = StaffMFADevice(user=user, confirmed_at=timezone.now())
        device.set_secret(secret)
        codes = generate_recovery_codes(device)
        device.save()
        return device, secret, codes

    def request(self, user):
        request = RequestFactory().post("/test/")
        request.user = user
        request.request_id = uuid.uuid4()
        return request

    def test_recovery_code_is_stored_as_digest_and_consumed_once(self):
        device, _, codes = self.device(self.staff())
        self.assertNotIn(codes[0].replace("-", ""), device.recovery_code_digests)
        accepted, used_recovery = verify_mfa_code(device, codes[0])
        replayed, _ = verify_mfa_code(device, codes[0])
        self.assertTrue(accepted)
        self.assertTrue(used_recovery)
        self.assertFalse(replayed)

    def test_confirmed_replacement_revokes_old_authenticator(self):
        user = self.staff()
        old, _, _ = self.device(user)
        request = self.request(user)
        replacement, secret, recovery_codes = start_mfa_replacement(request)
        self.assertEqual(len(recovery_codes), 10)
        confirmation_code = pyotp.TOTP(secret).now()
        self.assertTrue(confirm_mfa_replacement(request, replacement, confirmation_code))
        old.refresh_from_db()
        replacement.refresh_from_db()
        self.assertIsNotNone(old.revoked_at)
        self.assertIsNotNone(replacement.confirmed_at)
        self.assertEqual(verify_mfa_code(replacement, confirmation_code), (False, False))

    def test_new_account_token_invalidates_prior_and_consumption_invalidates_siblings(self):
        user = self.staff()
        first = issue_account_token(user, AccountToken.Purpose.RESET_PASSWORD)
        second = issue_account_token(user, AccountToken.Purpose.RESET_PASSWORD)
        with self.assertRaises(Conflict):
            from accounts.services import consume_account_token

            consume_account_token(first, AccountToken.Purpose.RESET_PASSWORD)
        from accounts.services import consume_account_token

        self.assertEqual(consume_account_token(second, AccountToken.Purpose.RESET_PASSWORD), user)

    def test_forgot_password_rolls_back_token_rotation_when_outbox_insert_fails(self):
        user = self.staff()
        old_raw = issue_account_token(user, AccountToken.Purpose.RESET_PASSWORD)
        old = AccountToken.objects.get(token_digest=__import__("hashlib").sha256(old_raw.encode()).hexdigest())
        with patch("communications.services.enqueue_email", side_effect=RuntimeError("synthetic outbox failure")):
            response = APIClient().post(
                "/api/v1/auth/password/forgot/",
                {"email": user.email},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        old.refresh_from_db()
        self.assertIsNone(old.used_at)
        self.assertEqual(AccountToken.objects.filter(user=user, purpose=AccountToken.Purpose.RESET_PASSWORD).count(), 1)
