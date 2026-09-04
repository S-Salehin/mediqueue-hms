import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


def postgres_config(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
        "TEST": {"NAME": os.environ.get("TEST_DATABASE_NAME") or None},
    }


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "development-only-change-before-deployment")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CSRF_FAILURE_VIEW = "core.csrf.csrf_failure"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "accounts",
    "directory",
    "operations",
    "communications",
    "help_assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.SessionLifetimeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": postgres_config(
        os.environ.get(
            "DATABASE_URL",
            "postgresql://mediqueue:mediqueue@localhost:5432/mediqueue",
        )
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

SECURE_COOKIES = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
SESSION_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = False
SESSION_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_IDLE_TIMEOUT_SECONDS", "1800"))
SESSION_ABSOLUTE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_ABSOLUTE_TIMEOUT_SECONDS", "28800"))
MFA_CHALLENGE_TIMEOUT_SECONDS = int(os.environ.get("MFA_CHALLENGE_TIMEOUT_SECONDS", "600"))
CSRF_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if env_bool("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.IsAuthenticatedWithStaffMFA"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.BoundedPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["core.throttling.DatabaseScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"auth": "60/min", "public": "1800/min", "write": "120/min", "assistant": "20/min"},
}

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USERNAME", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = env_bool("SMTP_USE_TLS", True)
EMAIL_TIMEOUT = max(1, min(60, int(os.environ.get("SMTP_TIMEOUT_SECONDS", "10"))))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Hospital service <noreply@example.test>")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173")

APP_VERSION = os.environ.get("APP_VERSION", "development")
OUTBOX_POLL_SECONDS = int(os.environ.get("OUTBOX_POLL_SECONDS", "5"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_TIMEOUT_SECONDS = max(2, min(20, int(os.environ.get("GROQ_TIMEOUT_SECONDS", "8"))))
# Groq sits behind an edge filter that rejects the default urllib agent, so the client identifies itself.
GROQ_USER_AGENT = os.environ.get("GROQ_USER_AGENT", f"MediQueue-HelpAssistant/{APP_VERSION}").strip()
# Reasoning models spend the completion budget on hidden reasoning unless the effort is bounded.
GROQ_REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "low").strip()
MFA_ENCRYPTION_KEY = os.environ.get("MFA_ENCRYPTION_KEY", "")
if not DEBUG and not MFA_ENCRYPTION_KEY:
    raise RuntimeError("MFA_ENCRYPTION_KEY is required when DJANGO_DEBUG is false")
if not DEBUG:
    from config.production_safety import validate_production_configuration

    validate_production_configuration(
        secret_key=SECRET_KEY,
        mfa_key=MFA_ENCRYPTION_KEY,
        allowed_hosts=ALLOWED_HOSTS,
        secure_cookies=SESSION_COOKIE_SECURE,
        ssl_redirect=SECURE_SSL_REDIRECT,
        idle_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
        absolute_seconds=SESSION_ABSOLUTE_TIMEOUT_SECONDS,
        allow_insecure_test=env_bool("ALLOW_INSECURE_TEST_SETTINGS", False),
        app_version=APP_VERSION,
        database_name=DATABASES["default"]["NAME"],
        database_host=DATABASES["default"]["HOST"],
    )
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
FILE_UPLOAD_MAX_MEMORY_SIZE = 1_048_576

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.logging.JSONFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
