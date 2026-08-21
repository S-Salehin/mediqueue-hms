from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches


class ProductionRouteSecurityTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_django_admin_route_is_not_exposed_in_production(self):
        import importlib

        from config import urls

        try:
            clear_url_caches()
            production_urls = importlib.reload(urls)
            self.assertFalse(any(getattr(pattern, "pattern", None)._route == "django-admin/" for pattern in production_urls.urlpatterns))
        finally:
            clear_url_caches()
            importlib.reload(urls)
