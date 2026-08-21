#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --environment staging|production --env-file /absolute/path.env --release release-id --confirm DEPLOY:environment:release-id\n' "$0"
}

ENVIRONMENT=''
ENV_FILE=''
RELEASE=''
CONFIRMATION=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --release) RELEASE="${2:-}"; shift 2 ;;
        --confirm) CONFIRMATION="${2:-}"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) usage >&2; die "Unknown argument: $1" ;;
    esac
done

[[ "${ENVIRONMENT}" == 'staging' || "${ENVIRONMENT}" == 'production' ]] \
    || die 'Environment must be staging or production.'
[[ "${RELEASE}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$ ]] || die 'Release identifier has an invalid format.'
assert_confirmation "${CONFIRMATION}" "DEPLOY:${ENVIRONMENT}:${RELEASE}"
assert_environment_file "${ENVIRONMENT}" "${ENV_FILE}"
[[ "$(read_env_value RELEASE_ID "${ENV_FILE}")" == "${RELEASE}" ]] \
    || die 'Release identifier does not match RELEASE_ID in the environment file.'
check_production_configuration
acquire_operation_lock deploy

DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
cleanup_registry_session() {
    docker logout ghcr.io >/dev/null 2>&1 || true
    rm -f -- "${DOCKER_CONFIG}/config.json"
    rmdir -- "${DOCKER_CONFIG}" 2>/dev/null || true
}
trap cleanup_registry_session EXIT

GHCR_USERNAME="$(read_env_value GHCR_USERNAME "${ENV_FILE}")"
GHCR_TOKEN="$(read_env_value GHCR_TOKEN "${ENV_FILE}")"
printf '%s' "${GHCR_TOKEN}" | docker login ghcr.io --username "${GHCR_USERNAME}" --password-stdin >/dev/null

note "Pulling immutable images for ${RELEASE}."
APP_IMAGE="$(read_env_value APP_IMAGE "${ENV_FILE}")"
WEB_IMAGE="$(read_env_value WEB_IMAGE "${ENV_FILE}")"
DATABASE_IMAGE="$(read_env_value DATABASE_IMAGE "${ENV_FILE}")"
assert_compose_image_set "${APP_IMAGE}" "${WEB_IMAGE}" "${DATABASE_IMAGE}"
compose_production pull
APP_VERSION="$(read_env_value APP_VERSION "${ENV_FILE}")"
assert_image_revision "${APP_IMAGE}" "${APP_VERSION}" APP_IMAGE
assert_image_revision "${WEB_IMAGE}" "${APP_VERSION}" WEB_IMAGE
assert_image_revision "${DATABASE_IMAGE}" "${APP_VERSION}" DATABASE_IMAGE
note 'All pulled images match the reviewed source commit.'

note 'Starting the database and backup control service.'
compose_production up --detach --wait --wait-timeout 240 db backup

note 'Creating and verifying the predeployment recovery point.'
bash "${SCRIPT_DIR}/backup.sh" --environment "${ENVIRONMENT}" --env-file "${ENV_FILE}" \
    --type incr --confirm "BACKUP:${ENVIRONMENT}"

note 'Running deployment checks and reviewing the migration plan.'
MIGRATION_DATABASE_URL="$(read_env_value MIGRATION_DATABASE_URL "${ENV_FILE}")"
compose_production run --rm --no-deps --env "DATABASE_URL=${MIGRATION_DATABASE_URL}" api python manage.py check --deploy
compose_production run --rm --no-deps --env "DATABASE_URL=${MIGRATION_DATABASE_URL}" api python manage.py showmigrations --plan
compose_production run --rm --no-deps --env "DATABASE_URL=${MIGRATION_DATABASE_URL}" api python manage.py migrate --noinput

note 'Starting the application services in dependency order.'
compose_production up --detach --wait --wait-timeout 180 api
compose_production up --detach --wait --wait-timeout 180 worker web
bash "${SCRIPT_DIR}/smoke-test.sh" --environment "${ENVIRONMENT}" --env-file "${ENV_FILE}"

compose_production ps
note "Deployment ${RELEASE} passed automated readiness and smoke checks."
note 'Observe error rate, latency, outbox age, database connections, and disk use for at least 15 minutes before closing the change.'
