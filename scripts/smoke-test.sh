#!/usr/bin/env bash

set -Eeuo pipefail
source "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    printf 'Usage: %s --environment staging|production --env-file /absolute/path.env\n' "$0"
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
require_command curl

PUBLIC_BASE_URL="$(read_env_value PUBLIC_BASE_URL "${ENV_FILE}")"
REAL_DATA_APPROVED="$(read_env_value REAL_DATA_APPROVED "${ENV_FILE}")"
CURL_OPTIONS=(--fail --silent --show-error --location --max-time 10 --retry 2 --retry-connrefused)

curl "${CURL_OPTIONS[@]}" "${PUBLIC_BASE_URL}/api/v1/health/live/" >/dev/null
curl "${CURL_OPTIONS[@]}" "${PUBLIC_BASE_URL}/api/v1/health/ready/" >/dev/null
curl "${CURL_OPTIONS[@]}" "${PUBLIC_BASE_URL}/" >/dev/null
note "Public liveness, readiness, and application shell checks passed for ${ENVIRONMENT}."

if [[ "${REAL_DATA_APPROVED}" == 'true' ]]; then
    HOSPITAL_RESPONSE="$(curl "${CURL_OPTIONS[@]}" "${PUBLIC_BASE_URL}/api/v1/public/hospital/")"
    printf '%s' "${HOSPITAL_RESPONSE}" | grep --extended-regexp --quiet '"privacy_notice"[[:space:]]*:[[:space:]]*\{' \
        || die 'Real data approval requires an active public privacy notice.'
    note 'The approved real data environment exposes an active privacy notice.'
fi
