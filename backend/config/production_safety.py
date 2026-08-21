def validate_production_configuration(
    *,
    secret_key,
    mfa_key,
    allowed_hosts,
    secure_cookies,
    ssl_redirect,
    idle_seconds,
    absolute_seconds,
    allow_insecure_test,
    app_version,
    database_name,
    database_host,
):
    if len(secret_key) < 50 or "change_me" in secret_key.lower() or "development-only" in secret_key.lower():
        raise RuntimeError("DJANGO_SECRET_KEY must be a non-placeholder value of at least 50 characters.")
    if len(mfa_key) < 32 or "change_me" in mfa_key.lower():
        raise RuntimeError("MFA_ENCRYPTION_KEY must be a non-placeholder value of at least 32 characters.")
    if mfa_key == secret_key:
        raise RuntimeError("MFA_ENCRYPTION_KEY must be different from DJANGO_SECRET_KEY.")
    if not allowed_hosts or "*" in allowed_hosts:
        raise RuntimeError("DJANGO_ALLOWED_HOSTS must contain explicit approved hosts.")
    if not 300 <= idle_seconds <= 3600:
        raise RuntimeError("SESSION_IDLE_TIMEOUT_SECONDS must be between 300 and 3600.")
    if not 3600 <= absolute_seconds <= 28800 or absolute_seconds <= idle_seconds:
        raise RuntimeError("The absolute session timeout must be 3600 to 28800 and longer than idle.")
    if secure_cookies and ssl_redirect:
        return
    synthetic_database = "test" in database_name.lower() or "ci" in database_name.lower()
    synthetic_host = database_host.lower() in {"localhost", "127.0.0.1", "db"}
    if not (allow_insecure_test and app_version.lower() in {"test", "ci"} and synthetic_database and synthetic_host):
        raise RuntimeError("Secure cookies and HTTPS redirect are required outside a bounded synthetic test environment.")
