#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --environment staging|production --env-file /absolute/path.env --release prior-release --app-version reviewed-commit --app-image image@sha256:... --web-image image@sha256:... --schema-compatible confirmed --confirm ROLLBACK:environment:prior-release\n' "$0"
}

ENVIRONMENT=''
ENV_FILE=''
RELEASE=''
PREVIOUS_APP_IMAGE=''
PREVIOUS_WEB_IMAGE=''
PREVIOUS_APP_VERSION=''
SCHEMA_COMPATIBLE=''
CONFIRMATION=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --release) RELEASE="${2:-}"; shift 2 ;;
        --app-image) PREVIOUS_APP_IMAGE="${2:-}"; shift 2 ;;
        --web-image) PREVIOUS_WEB_IMAGE="${2:-}"; shift 2 ;;
        --app-version) PREVIOUS_APP_VERSION="${2:-}"; shift 2 ;;
        --schema-compatible) SCHEMA_COMPATIBLE="${2:-}"; shift 2 ;;
        --confirm) CONFIRMATION="${2:-}"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) usage >&2; die "Unknown argument: $1" ;;
    esac
done

[[ "${ENVIRONMENT}" == 'staging' || "${ENVIRONMENT}" == 'production' ]] \
    || die 'Environment must be staging or production.'
[[ "${RELEASE}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$ ]] || die 'Release identifier has an invalid format.'
assert_confirmation "${CONFIRMATION}" "ROLLBACK:${ENVIRONMENT}:${RELEASE}"
[[ "${SCHEMA_COMPATIBLE}" == 'confirmed' ]] \
    || die 'Schema compatibility must be reviewed and passed as --schema-compatible confirmed. Use the isolated restore procedure otherwise.'
assert_environment_file "${ENVIRONMENT}" "${ENV_FILE}"
check_production_configuration
assert_digest_reference "${PREVIOUS_APP_IMAGE}" APP_IMAGE
assert_digest_reference "${PREVIOUS_WEB_IMAGE}" WEB_IMAGE
[[ "${PREVIOUS_APP_VERSION}" =~ ^[a-f0-9]{40}$ ]] \
    || die '--app-version must be the full lower case 40 character reviewed Git commit for the prior release.'
acquire_operation_lock deploy

export APP_IMAGE="${PREVIOUS_APP_IMAGE}"
export WEB_IMAGE="${PREVIOUS_WEB_IMAGE}"
export APP_VERSION="${PREVIOUS_APP_VERSION}"

note "Pulling the recorded application images for ${RELEASE}."
assert_compose_image_set \
    "${PREVIOUS_APP_IMAGE}" \
    "${PREVIOUS_WEB_IMAGE}" \
    "$(read_env_value DATABASE_IMAGE "${ENV_FILE}")"
compose_production pull api worker web
assert_image_revision "${PREVIOUS_APP_IMAGE}" "${PREVIOUS_APP_VERSION}" APP_IMAGE
assert_image_revision "${PREVIOUS_WEB_IMAGE}" "${PREVIOUS_APP_VERSION}" WEB_IMAGE
note 'Both rollback images match the recorded prior source commit.'
compose_production run --rm --no-deps api python manage.py check --deploy
compose_production up --detach --wait --wait-timeout 180 api
compose_production up --detach --wait --wait-timeout 180 worker web
bash "${SCRIPT_DIR}/smoke-test.sh" --environment "${ENVIRONMENT}" --env-file "${ENV_FILE}"
compose_production ps
note "Image rollback to ${RELEASE} completed without changing the database schema."
