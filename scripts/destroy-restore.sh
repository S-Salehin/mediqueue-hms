#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --env-file /absolute/path.env --target-project mediqueue-restore-name --confirm DESTROY:target-project\n' "$0"
}

ENV_FILE=''
TARGET_PROJECT=''
CONFIRMATION=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --target-project) TARGET_PROJECT="${2:-}"; shift 2 ;;
        --confirm) CONFIRMATION="${2:-}"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) usage >&2; die "Unknown argument: $1" ;;
    esac
done

[[ "${TARGET_PROJECT}" =~ ^mediqueue-restore-[a-z0-9][a-z0-9-]{2,40}$ ]] \
    || die 'Only an isolated mediqueue-restore-* project can be destroyed.'
assert_confirmation "${CONFIRMATION}" "DESTROY:${TARGET_PROJECT}"
require_file "${ENV_FILE}"

SOURCE_PROJECT="$(read_env_value COMPOSE_PROJECT_NAME "${ENV_FILE}")"
[[ "${TARGET_PROJECT}" != "${SOURCE_PROJECT}" ]] || die 'The source project cannot be destroyed by this script.'

export COMPOSE_PROJECT_NAME="${TARGET_PROJECT}"
compose_production down --volumes --remove-orphans
note "Isolated restore project ${TARGET_PROJECT} and its project volumes were removed. Backup source data was not removed."
