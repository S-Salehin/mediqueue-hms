#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --environment staging|production --env-file /absolute/path/to/environment.env\n' "$0"
}

ENVIRONMENT=''
ENV_FILE=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) usage >&2; die "Unknown argument: $1" ;;
    esac
done

[[ "${ENVIRONMENT}" == 'staging' || "${ENVIRONMENT}" == 'production' ]] \
    || die 'Environment must be staging or production.'
assert_environment_file "${ENVIRONMENT}" "${ENV_FILE}"
check_production_configuration

APP_IMAGE="$(read_env_value APP_IMAGE "${ENV_FILE}")"
WEB_IMAGE="$(read_env_value WEB_IMAGE "${ENV_FILE}")"
DATABASE_IMAGE="$(read_env_value DATABASE_IMAGE "${ENV_FILE}")"
APP_VERSION="$(read_env_value APP_VERSION "${ENV_FILE}")"
BACKUP_REPOSITORY_PATH="$(read_env_value BACKUP_REPOSITORY_PATH "${ENV_FILE}")"
PUBLIC_BASE_URL="$(read_env_value PUBLIC_BASE_URL "${ENV_FILE}")"
PUBLIC_HOSTNAME="$(read_env_value PUBLIC_HOSTNAME "${ENV_FILE}")"
DJANGO_ALLOWED_HOSTS="$(read_env_value DJANGO_ALLOWED_HOSTS "${ENV_FILE}")"
DJANGO_CSRF_TRUSTED_ORIGINS="$(read_env_value DJANGO_CSRF_TRUSTED_ORIGINS "${ENV_FILE}")"
DJANGO_DEBUG="$(read_env_value DJANGO_DEBUG "${ENV_FILE}")"
DJANGO_SECURE_COOKIES="$(read_env_value DJANGO_SECURE_COOKIES "${ENV_FILE}")"
DJANGO_SECRET_KEY="$(read_env_value DJANGO_SECRET_KEY "${ENV_FILE}")"
MFA_ENCRYPTION_KEY="$(read_env_value MFA_ENCRYPTION_KEY "${ENV_FILE}")"
POSTGRES_DB="$(read_env_value POSTGRES_DB "${ENV_FILE}")"
POSTGRES_USER="$(read_env_value POSTGRES_USER "${ENV_FILE}")"
POSTGRES_PASSWORD="$(read_env_value POSTGRES_PASSWORD "${ENV_FILE}")"
MEDIQUEUE_MIGRATION_USER="$(read_env_value MEDIQUEUE_MIGRATION_USER "${ENV_FILE}")"
MEDIQUEUE_MIGRATION_PASSWORD="$(read_env_value MEDIQUEUE_MIGRATION_PASSWORD "${ENV_FILE}")"
MEDIQUEUE_APP_USER="$(read_env_value MEDIQUEUE_APP_USER "${ENV_FILE}")"
MEDIQUEUE_APP_PASSWORD="$(read_env_value MEDIQUEUE_APP_PASSWORD "${ENV_FILE}")"
DATABASE_URL="$(read_env_value DATABASE_URL "${ENV_FILE}")"
MIGRATION_DATABASE_URL="$(read_env_value MIGRATION_DATABASE_URL "${ENV_FILE}")"
SMTP_PASSWORD="$(read_env_value SMTP_PASSWORD "${ENV_FILE}")"
EMAIL_BACKEND="$(read_env_value EMAIL_BACKEND "${ENV_FILE}")"
SMTP_HOST="$(read_env_value SMTP_HOST "${ENV_FILE}")"
SMTP_USE_TLS="$(read_env_value SMTP_USE_TLS "${ENV_FILE}")"
BACKUP_ENCRYPTION_PASSPHRASE="$(read_env_value BACKUP_ENCRYPTION_PASSPHRASE "${ENV_FILE}")"
BACKUP_RETENTION_DAYS="$(read_env_value BACKUP_RETENTION_DAYS "${ENV_FILE}")"
SESSION_IDLE_TIMEOUT_SECONDS="$(read_env_value SESSION_IDLE_TIMEOUT_SECONDS "${ENV_FILE}")"
SESSION_ABSOLUTE_TIMEOUT_SECONDS="$(read_env_value SESSION_ABSOLUTE_TIMEOUT_SECONDS "${ENV_FILE}")"
GHCR_TOKEN="$(read_env_value GHCR_TOKEN "${ENV_FILE}")"
GROQ_API_KEY="$(read_env_value GROQ_API_KEY "${ENV_FILE}")"
GROQ_PROCESSOR_APPROVED="$(read_env_value GROQ_PROCESSOR_APPROVED "${ENV_FILE}")"
REAL_DATA_APPROVED="$(read_env_value REAL_DATA_APPROVED "${ENV_FILE}")"
OFF_HOST_BACKUP_APPROVED="$(read_env_value OFF_HOST_BACKUP_APPROVED "${ENV_FILE}")"

assert_digest_reference "${APP_IMAGE}" APP_IMAGE
assert_digest_reference "${WEB_IMAGE}" WEB_IMAGE
assert_digest_reference "${DATABASE_IMAGE}" DATABASE_IMAGE
[[ "${APP_VERSION}" =~ ^[a-f0-9]{40}$ ]] \
    || die 'APP_VERSION must be the full lower case 40 character reviewed Git commit.'
assert_safe_backup_path "${BACKUP_REPOSITORY_PATH}"
[[ "${DJANGO_DEBUG}" == 'false' ]] || die 'DJANGO_DEBUG must be false.'
[[ "${DJANGO_SECURE_COOKIES}" == 'true' ]] || die 'DJANGO_SECURE_COOKIES must be true.'
[[ "${BACKUP_RETENTION_DAYS}" == '30' ]] || die 'BACKUP_RETENTION_DAYS must remain 30 for the approved pilot policy.'
[[ "${SESSION_IDLE_TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] \
    || die 'SESSION_IDLE_TIMEOUT_SECONDS must be a whole number.'
[[ "${SESSION_ABSOLUTE_TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] \
    || die 'SESSION_ABSOLUTE_TIMEOUT_SECONDS must be a whole number.'
(( SESSION_IDLE_TIMEOUT_SECONDS >= 300 && SESSION_IDLE_TIMEOUT_SECONDS <= 3600 )) \
    || die 'SESSION_IDLE_TIMEOUT_SECONDS must be between 300 and 3600 seconds.'
(( SESSION_ABSOLUTE_TIMEOUT_SECONDS >= 3600 && SESSION_ABSOLUTE_TIMEOUT_SECONDS <= 28800 )) \
    || die 'SESSION_ABSOLUTE_TIMEOUT_SECONDS must be between 3600 and 28800 seconds.'
(( SESSION_ABSOLUTE_TIMEOUT_SECONDS > SESSION_IDLE_TIMEOUT_SECONDS )) \
    || die 'The absolute session timeout must be longer than the idle timeout.'
for database_identifier in "${POSTGRES_DB}" "${POSTGRES_USER}" "${MEDIQUEUE_MIGRATION_USER}" "${MEDIQUEUE_APP_USER}"; do
    [[ "${database_identifier}" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] \
        || die 'Database names and roles must use lower case PostgreSQL identifiers.'
done
[[ "${POSTGRES_USER}" != "${MEDIQUEUE_MIGRATION_USER}" \
    && "${POSTGRES_USER}" != "${MEDIQUEUE_APP_USER}" \
    && "${MEDIQUEUE_MIGRATION_USER}" != "${MEDIQUEUE_APP_USER}" ]] \
    || die 'Bootstrap, migration, and runtime database roles must be different.'
require_command python3
export MEDIQUEUE_VALIDATE_DATABASE_URL="${DATABASE_URL}"
export MEDIQUEUE_VALIDATE_DATABASE_USER="${MEDIQUEUE_APP_USER}"
export MEDIQUEUE_VALIDATE_DATABASE_PASSWORD="${MEDIQUEUE_APP_PASSWORD}"
export MEDIQUEUE_VALIDATE_MIGRATION_URL="${MIGRATION_DATABASE_URL}"
export MEDIQUEUE_VALIDATE_MIGRATION_USER="${MEDIQUEUE_MIGRATION_USER}"
export MEDIQUEUE_VALIDATE_MIGRATION_PASSWORD="${MEDIQUEUE_MIGRATION_PASSWORD}"
export MEDIQUEUE_VALIDATE_DATABASE_NAME="${POSTGRES_DB}"
python3 - <<'PY'
import os
import sys
from urllib.parse import unquote, urlsplit


def reject(message):
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_url(value, expected_user, expected_password, label):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        reject(f"{label} is not a valid PostgreSQL URL.")
    if parsed.scheme not in {"postgres", "postgresql"}:
        reject(f"{label} must use the PostgreSQL scheme.")
    if unquote(parsed.username or "") != expected_user:
        reject(f"{label} does not use its approved database role.")
    if unquote(parsed.password or "") != expected_password:
        reject(f"{label} password does not match its approved role password.")
    if (parsed.hostname or "").lower() != "db" or port != 5432:
        reject(f"{label} must use the internal db service on port 5432.")
    if unquote(parsed.path.lstrip("/")) != os.environ["MEDIQUEUE_VALIDATE_DATABASE_NAME"]:
        reject(f"{label} does not use the approved database name.")
    if parsed.query or parsed.fragment:
        reject(f"{label} must not contain query parameters or a fragment.")


validate_url(
    os.environ["MEDIQUEUE_VALIDATE_DATABASE_URL"],
    os.environ["MEDIQUEUE_VALIDATE_DATABASE_USER"],
    os.environ["MEDIQUEUE_VALIDATE_DATABASE_PASSWORD"],
    "DATABASE_URL",
)
validate_url(
    os.environ["MEDIQUEUE_VALIDATE_MIGRATION_URL"],
    os.environ["MEDIQUEUE_VALIDATE_MIGRATION_USER"],
    os.environ["MEDIQUEUE_VALIDATE_MIGRATION_PASSWORD"],
    "MIGRATION_DATABASE_URL",
)
PY
unset MEDIQUEUE_VALIDATE_DATABASE_URL MEDIQUEUE_VALIDATE_DATABASE_USER \
    MEDIQUEUE_VALIDATE_DATABASE_PASSWORD MEDIQUEUE_VALIDATE_MIGRATION_URL \
    MEDIQUEUE_VALIDATE_MIGRATION_USER MEDIQUEUE_VALIDATE_MIGRATION_PASSWORD \
    MEDIQUEUE_VALIDATE_DATABASE_NAME
(( ${#POSTGRES_PASSWORD} >= 24 )) || die 'POSTGRES_PASSWORD must contain at least 24 characters.'
(( ${#MEDIQUEUE_MIGRATION_PASSWORD} >= 24 )) || die 'MEDIQUEUE_MIGRATION_PASSWORD must contain at least 24 characters.'
(( ${#MEDIQUEUE_APP_PASSWORD} >= 24 )) || die 'MEDIQUEUE_APP_PASSWORD must contain at least 24 characters.'
(( ${#DJANGO_SECRET_KEY} >= 50 )) || die 'DJANGO_SECRET_KEY must contain at least 50 characters.'
(( ${#MFA_ENCRYPTION_KEY} >= 32 )) || die 'MFA_ENCRYPTION_KEY must contain at least 32 characters.'
(( ${#BACKUP_ENCRYPTION_PASSPHRASE} >= 32 )) || die 'BACKUP_ENCRYPTION_PASSPHRASE must contain at least 32 characters.'
SECRET_LABELS=(DJANGO_SECRET_KEY MFA_ENCRYPTION_KEY POSTGRES_PASSWORD MEDIQUEUE_MIGRATION_PASSWORD MEDIQUEUE_APP_PASSWORD SMTP_PASSWORD BACKUP_ENCRYPTION_PASSPHRASE GHCR_TOKEN)
SECRET_VALUES=("${DJANGO_SECRET_KEY}" "${MFA_ENCRYPTION_KEY}" "${POSTGRES_PASSWORD}" "${MEDIQUEUE_MIGRATION_PASSWORD}" "${MEDIQUEUE_APP_PASSWORD}" "${SMTP_PASSWORD}" "${BACKUP_ENCRYPTION_PASSPHRASE}" "${GHCR_TOKEN}")
if [[ -n "${GROQ_API_KEY}" ]]; then
    (( ${#GROQ_API_KEY} >= 20 )) || die 'GROQ_API_KEY must contain at least 20 characters when configured.'
    SECRET_LABELS+=(GROQ_API_KEY)
    SECRET_VALUES+=("${GROQ_API_KEY}")
fi
for ((left = 0; left < ${#SECRET_VALUES[@]}; left += 1)); do
    for ((right = left + 1; right < ${#SECRET_VALUES[@]}; right += 1)); do
        [[ "${SECRET_VALUES[left]}" != "${SECRET_VALUES[right]}" ]] \
            || die "${SECRET_LABELS[left]} and ${SECRET_LABELS[right]} must not reuse the same value."
    done
done
[[ "${PUBLIC_HOSTNAME}" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] \
    || die 'PUBLIC_HOSTNAME must be a hostname without a scheme, path, or port.'
[[ "${DJANGO_ALLOWED_HOSTS}" == "${PUBLIC_HOSTNAME}" ]] \
    || die 'DJANGO_ALLOWED_HOSTS must contain only PUBLIC_HOSTNAME for this single-host pilot.'
[[ "${DJANGO_CSRF_TRUSTED_ORIGINS}" == "https://${PUBLIC_HOSTNAME}" ]] \
    || die 'DJANGO_CSRF_TRUSTED_ORIGINS must contain only the exact HTTPS public origin.'
[[ "${PUBLIC_BASE_URL}" == "https://${PUBLIC_HOSTNAME}" ]] \
    || die 'PUBLIC_BASE_URL must be the exact HTTPS public origin.'
[[ "${EMAIL_BACKEND}" == 'django.core.mail.backends.smtp.EmailBackend' ]] \
    || die 'Staging and production must use the SMTP email backend.'
[[ "${SMTP_USE_TLS}" == 'true' ]] || die 'SMTP_USE_TLS must be true.'
[[ "${REAL_DATA_APPROVED}" == 'true' || "${REAL_DATA_APPROVED}" == 'false' ]] \
    || die 'REAL_DATA_APPROVED must be true or false.'
[[ "${OFF_HOST_BACKUP_APPROVED}" == 'true' || "${OFF_HOST_BACKUP_APPROVED}" == 'false' ]] \
    || die 'OFF_HOST_BACKUP_APPROVED must be true or false.'
[[ "${GROQ_PROCESSOR_APPROVED}" == 'true' || "${GROQ_PROCESSOR_APPROVED}" == 'false' ]] \
    || die 'GROQ_PROCESSOR_APPROVED must be true or false.'

if [[ "${REAL_DATA_APPROVED}" == 'true' && "${OFF_HOST_BACKUP_APPROVED}" != 'true' ]]; then
    die 'Real data approval requires approved off-host backup replication.'
fi

if [[ "${REAL_DATA_APPROVED}" == 'true' && -n "${GROQ_API_KEY}" && "${GROQ_PROCESSOR_APPROVED}" != 'true' ]]; then
    die 'Groq must remain disabled for real data until GROQ_PROCESSOR_APPROVED is true.'
fi

if [[ "${ENVIRONMENT}" == 'production' && "${REAL_DATA_APPROVED}" == 'true' ]]; then
    [[ "${PUBLIC_HOSTNAME}" == *.* \
        && ! "${PUBLIC_HOSTNAME}" =~ (^|\.)localhost$ \
        && ! "${PUBLIC_HOSTNAME}" =~ \.(example|invalid|local|test)$ \
        && ! "${PUBLIC_HOSTNAME}" =~ ^[0-9.]+$ ]] \
        || die 'An approved real data production host must use a public hospital domain.'
    [[ "${SMTP_HOST}" != 'localhost' && "${SMTP_HOST}" != '127.0.0.1' ]] \
        || die 'A real data production environment must use the approved external SMTP host.'
fi

if [[ "${ENVIRONMENT}" == 'staging' && "${REAL_DATA_APPROVED}" != 'false' ]]; then
    die 'Staging is restricted to synthetic data. REAL_DATA_APPROVED must be false.'
fi

if [[ "${REAL_DATA_APPROVED}" != 'true' ]]; then
    note 'Real data approval is false. This environment is restricted to synthetic data.'
fi

note "${ENVIRONMENT} configuration is structurally valid."
