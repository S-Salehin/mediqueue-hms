#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --environment staging|production --env-file /absolute/path.env --type full|incr --confirm BACKUP:environment\n' "$0"
}

ENVIRONMENT=''
ENV_FILE=''
BACKUP_TYPE=''
CONFIRMATION=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --type) BACKUP_TYPE="${2:-}"; shift 2 ;;
        --confirm) CONFIRMATION="${2:-}"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) usage >&2; die "Unknown argument: $1" ;;
    esac
done

[[ "${ENVIRONMENT}" == 'staging' || "${ENVIRONMENT}" == 'production' ]] \
    || die 'Environment must be staging or production.'
[[ "${BACKUP_TYPE}" == 'full' || "${BACKUP_TYPE}" == 'incr' ]] \
    || die 'Backup type must be full or incr.'
assert_confirmation "${CONFIRMATION}" "BACKUP:${ENVIRONMENT}"
assert_environment_file "${ENVIRONMENT}" "${ENV_FILE}"
check_production_configuration
acquire_operation_lock backup

note "Starting ${BACKUP_TYPE} backup for ${ENVIRONMENT}."
compose_production up --detach --wait --wait-timeout 180 db backup
compose_production exec --no-TTY backup pgbackrest --stanza=mediqueue check
compose_production exec --no-TTY backup pgbackrest --stanza=mediqueue --type="${BACKUP_TYPE}" backup
compose_production exec --no-TTY backup pgbackrest --stanza=mediqueue verify
compose_production exec --no-TTY backup pgbackrest --stanza=mediqueue info
note 'Backup and repository verification completed.'
