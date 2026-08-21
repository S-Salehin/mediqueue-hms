from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import AccountToken, User
from accounts.services import digest_token
from communications.models import NotificationAttempt, NotificationOutbox
from communications.services import enqueue_email, process_one_outbox


class NotificationOutboxTests(TestCase):
    def account_token(self, raw, purpose):
        user = User.objects.create_user(
            f"{purpose}-{User.objects.count()}@example.test",
            "SyntheticOnly!2026",
            display_name="Synthetic User",
        )
        AccountToken.objects.create(
            user=user,
            purpose=purpose,
            token_digest=digest_token(raw),
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        return user

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_successful_delivery_records_attempt_and_clears_token(self):
        raw = "secret-token-for-test"
        user = self.account_token(raw, AccountToken.Purpose.VERIFY_EMAIL)
        job = enqueue_email(user.email, "verify_email", {"token": raw}, related_id=user.pk)
        self.assertTrue(process_one_outbox())
        job.refresh_from_db()
        self.assertEqual(job.state, NotificationOutbox.State.SENT)
        self.assertEqual(job.template_data, {})
        self.assertEqual(job.attempts.get().result, "sent")
        self.assertTrue(job.provider_reference)

    @patch("communications.services.send_mail", side_effect=TimeoutError("provider timeout"))
    def test_temporary_failure_retries_without_losing_business_job(self, mocked_send):
        job = enqueue_email("recipient@example.test", "appointment_booked", {"url": "/patient/appointments/synthetic"})
        self.assertTrue(process_one_outbox())
        job.refresh_from_db()
        self.assertEqual(job.state, NotificationOutbox.State.FAILED)
        self.assertEqual(job.attempt_count, 1)
        self.assertGreater(job.next_attempt_at, timezone.now())
        self.assertEqual(NotificationAttempt.objects.get(outbox=job).safe_error_category, "timeouterror")
        self.assertEqual(mocked_send.call_count, 1)

    @patch("communications.services.send_mail", side_effect=ValueError("permanent synthetic failure"))
    def test_fifth_failure_becomes_dead_and_removes_sensitive_template_data(self, mocked_send):
        raw = "temporary-reset-token"
        user = self.account_token(raw, AccountToken.Purpose.RESET_PASSWORD)
        job = enqueue_email(user.email, "reset_password", {"token": raw}, related_id=user.pk)
        job.attempt_count = 4
        job.save(update_fields=["attempt_count", "updated_at"])
        self.assertTrue(process_one_outbox())
        job.refresh_from_db()
        self.assertEqual(job.state, NotificationOutbox.State.DEAD)
        self.assertEqual(job.template_data, {})
        self.assertEqual(job.attempts.get().attempt_number, 5)

    @patch("communications.services.send_mail")
    def test_expired_secure_link_is_discarded_without_delivery(self, mocked_send):
        raw = "expired-reset-token"
        user = self.account_token(raw, AccountToken.Purpose.RESET_PASSWORD)
        AccountToken.objects.filter(user=user).update(expires_at=timezone.now() - timedelta(seconds=1))
        job = enqueue_email(user.email, "reset_password", {"token": raw}, related_id=user.pk)
        self.assertTrue(process_one_outbox())
        job.refresh_from_db()
        self.assertEqual(job.state, NotificationOutbox.State.DEAD)
        self.assertEqual(job.last_error_category, "expired_or_superseded")
        self.assertEqual(job.template_data, {})
        mocked_send.assert_not_called()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_abandoned_processing_lease_is_reclaimed(self):
        job = enqueue_email("recipient@example.test", "appointment_booked", {"url": "/patient/appointments/synthetic"})
        job.state = NotificationOutbox.State.PROCESSING
        job.leased_at = timezone.now() - __import__("datetime").timedelta(minutes=11)
        job.attempt_count = 1
        job.save(update_fields=["state", "leased_at", "attempt_count", "updated_at"])
        self.assertTrue(process_one_outbox())
        job.refresh_from_db()
        self.assertEqual(job.state, NotificationOutbox.State.SENT)
        self.assertEqual(job.attempt_count, 2)

    def test_expired_processing_lease_at_attempt_limit_is_marked_dead_without_send(self):
        job = enqueue_email("recipient@example.test", "reset_password", {"token": "do-not-send"})
        job.state = NotificationOutbox.State.PROCESSING
        job.leased_at = timezone.now() - __import__("datetime").timedelta(minutes=11)
        job.attempt_count = 5
        job.save(update_fields=["state", "leased_at", "attempt_count", "updated_at"])
        with patch("communications.services.send_mail") as send:
            self.assertTrue(process_one_outbox())
        job.refresh_from_db()
        self.assertEqual(job.state, NotificationOutbox.State.DEAD)
        self.assertEqual(job.template_data, {})
        send.assert_not_called()
