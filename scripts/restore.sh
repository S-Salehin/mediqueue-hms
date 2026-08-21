#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --environment staging|production --env-file /absolute/path.env --target-project mediqueue-restore-name [--target-time ISO8601] --confirm RESTORE:target-project\n' "$0"
}

ENVIRONMENT=''
ENV_FILE=''
TARGET_PROJECT=''
TARGET_TIME=''
CONFIRMATION=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --target-project) TARGET_PROJECT="${2:-}"; shift 2 ;;
        --target-time) TARGET_TIME="${2:-}"; shift 2 ;;
        --confirm) CONFIRMATION="${2:-}"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) usage >&2; die "Unknown argument: $1" ;;
    esac
done

[[ "${ENVIRONMENT}" == 'staging' || "${ENVIRONMENT}" == 'production' ]] \
    || die 'Environment must be staging or production.'
[[ "${TARGET_PROJECT}" =~ ^mediqueue-restore-[a-z0-9][a-z0-9-]{2,40}$ ]] \
    || die 'Target project must begin with mediqueue-restore- and contain only lowercase letters, numbers, and hyphens.'
assert_confirmation "${CONFIRMATION}" "RESTORE:${TARGET_PROJECT}"
assert_environment_file "${ENVIRONMENT}" "${ENV_FILE}"
check_production_configuration
acquire_operation_lock restore

SOURCE_PROJECT="$(read_env_value COMPOSE_PROJECT_NAME "${ENV_FILE}")"
[[ "${TARGET_PROJECT}" != "${SOURCE_PROJECT}" ]] || die 'Restore target cannot be the source project.'

TARGET_VOLUME="${TARGET_PROJECT}_postgres_data"
if docker volume inspect "${TARGET_VOLUME}" >/dev/null 2>&1; then
    die "Restore target volume already exists: ${TARGET_VOLUME}. Choose a new target project."
fi

export COMPOSE_PROJECT_NAME="${TARGET_PROJECT}"

note "Preparing isolated restore project ${TARGET_PROJECT}. No public service will be started."
compose_production run --rm --no-deps db-storage-init

RESTORE_ARGUMENTS=(--stanza=mediqueue --target-action=promote restore)
if [[ -n "${TARGET_TIME}" ]]; then
    RESTORE_ARGUMENTS=(--stanza=mediqueue --type=time --target="${TARGET_TIME}" --target-action=promote restore)
fi

compose_production run --rm --no-deps --user postgres --entrypoint pgbackrest db "${RESTORE_ARGUMENTS[@]}"
compose_production up --detach --wait --wait-timeout 180 db
compose_production exec --no-TTY db psql --username="$(read_env_value POSTGRES_USER "${ENV_FILE}")" \
    --dbname="$(read_env_value POSTGRES_DB "${ENV_FILE}")" \
    --tuples-only --command='select current_database(), pg_is_in_recovery();'

note "Restore completed in isolated project ${TARGET_PROJECT}."
note 'The API, worker, and web services were not started. Complete integrity checks before any application connection.'
note "When evidence is retained, use destroy-restore.sh with target ${TARGET_PROJECT}."
