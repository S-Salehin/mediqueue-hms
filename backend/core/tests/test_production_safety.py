from django.test import SimpleTestCase

from config.production_safety import validate_production_configuration


class ProductionSafetySettingsTests(SimpleTestCase):
    def valid(self, **changes):
        values = {
            "secret_key": "d" * 64,
            "mfa_key": "m" * 48,
            "allowed_hosts": ["pilot.example.test"],
            "secure_cookies": True,
            "ssl_redirect": True,
            "idle_seconds": 1800,
            "absolute_seconds": 28800,
            "allow_insecure_test": False,
            "app_version": "production-sha",
            "database_name": "mediqueue",
            "database_host": "db",
        }
        values.update(changes)
        return values

    def test_accepts_secure_distinct_secrets_and_bounded_sessions(self):
        validate_production_configuration(**self.valid())

    def test_rejects_weak_or_reused_secrets_and_wildcard_hosts(self):
        invalid = [
            {"secret_key": "short"},
            {"mfa_key": "short"},
            {"mfa_key": "d" * 64},
            {"allowed_hosts": []},
            {"allowed_hosts": ["*"]},
        ]
        for changes in invalid:
            with self.subTest(changes=sorted(changes)), self.assertRaises(RuntimeError):
                validate_production_configuration(**self.valid(**changes))

    def test_rejects_unsafe_session_bounds(self):
        for changes in (
            {"idle_seconds": 299},
            {"idle_seconds": 3601},
            {"absolute_seconds": 3599},
            {"absolute_seconds": 28801},
            {"idle_seconds": 3600, "absolute_seconds": 3600},
        ):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                validate_production_configuration(**self.valid(**changes))

    def test_insecure_transport_escape_is_limited_to_synthetic_database(self):
        synthetic = self.valid(
            secure_cookies=False,
            ssl_redirect=False,
            allow_insecure_test=True,
            app_version="test",
            database_name="mediqueue_test",
        )
        validate_production_configuration(**synthetic)
        with self.assertRaises(RuntimeError):
            validate_production_configuration(
                **{
                    **synthetic,
                    "database_name": "mediqueue",
                }
            )
