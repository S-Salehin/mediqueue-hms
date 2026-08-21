#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
PRODUCTION_COMPOSE_FILE="${REPOSITORY_ROOT}/compose.production.yml"

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

note() {
    printf '%s\n' "$*"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command is not installed: $1"
}

require_file() {
    [[ -n "${1:-}" ]] || die 'An environment file must be supplied explicitly.'
    [[ -f "$1" ]] || die "File does not exist: $1"
}

read_env_value() {
    local key="$1"
    local file="$2"
    local count
    local value

    count="$(awk -F= -v key="${key}" '$0 !~ /^[[:space:]]*#/ && $1 == key { count += 1 } END { print count + 0 }' "${file}")"
    [[ "${count}" == '1' ]] || die "${file} must contain exactly one ${key}= entry."
    value="$(awk -F= -v key="${key}" '$0 !~ /^[[:space:]]*#/ && $1 == key { sub(/^[^=]*=/, ""); print; exit }' "${file}")"
    [[ -n "${value}" ]] || die "${key} must not be blank in ${file}."
    printf '%s' "${value}"
}

assert_environment_file() {
    local expected="$1"
    local file="$2"
    local actual

    require_file "${file}"
    actual="$(read_env_value DEPLOY_ENVIRONMENT "${file}")"
    [[ "${actual}" == "${expected}" ]] || die "Environment mismatch. Expected ${expected}, found ${actual}."

    if [[ "${expected}" == 'production' ]] && command -v stat >/dev/null 2>&1; then
        local mode
        local owner
        mode="$(stat -c '%a' "${file}" 2>/dev/null || true)"
        owner="$(stat -c '%U' "${file}" 2>/dev/null || true)"
        if [[ -n "${mode}" && "${mode}" != '600' && "${mode}" != '640' ]]; then
            die "Production environment file permissions are too broad (${mode}). Use mode 600 or root-owned mode 640 with a dedicated deployment group."
        fi
        if [[ "${mode}" == '640' && "${owner}" != 'root' ]]; then
            die 'A mode 640 production environment file must be owned by root.'
        fi
    fi
}

assert_confirmation() {
    local actual="${1:-}"
    local expected="$2"
    [[ "${actual}" == "${expected}" ]] || die "Confirmation must be exactly ${expected}."
}

assert_digest_reference() {
    local reference="$1"
    local label="$2"
    [[ "${reference}" =~ ^[a-zA-Z0-9._/-]+@sha256:[a-fA-F0-9]{64}$ ]] \
        || die "${label} must be an immutable image reference ending in @sha256:<64 hex characters>."
}

assert_image_revision() {
    local reference="$1"
    local expected_revision="$2"
    local label="$3"
    local actual_revision

    assert_digest_reference "${reference}" "${label}"
    [[ "${expected_revision}" =~ ^[a-f0-9]{40}$ ]] \
        || die 'APP_VERSION must be the full lower case 40 character reviewed Git commit.'
    actual_revision="$(docker image inspect "${reference}" \
        --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>/dev/null)" \
        || die "${label} is not available locally after the image pull."
    [[ "${actual_revision}" == "${expected_revision}" ]] \
        || die "${label} was not built from the approved APP_VERSION."
}

assert_compose_image_set() {
    local app_image="$1"
    local web_image="$2"
    local database_image="$3"
    local expected
    local resolved

    expected="$(printf '%s\n' "${app_image}" "${web_image}" "${database_image}" | sort -u)"
    resolved="$(compose_production config --images | sort -u)"
    [[ "${resolved}" == "${expected}" ]] \
        || die 'Resolved Compose images do not exactly match the three approved environment file digests.'
}

assert_safe_backup_path() {
    local path="$1"
    local resolved
    local repository_resolved
    [[ "${path}" == /* ]] || die 'BACKUP_REPOSITORY_PATH must be absolute.'
    [[ -d "${path}" ]] || die "Backup repository directory does not exist: ${path}"
    require_command realpath
    resolved="$(realpath -e -- "${path}")"
    repository_resolved="$(realpath -e -- "${REPOSITORY_ROOT}")"
    case "${resolved}" in
        /|/bin|/boot|/dev|/etc|/home|/lib|/lib64|/media|/mnt|/opt|/proc|/root|/run|/sbin|/srv|/sys|/tmp|/usr|/var)
            die 'BACKUP_REPOSITORY_PATH resolves to a system directory that is too broad.'
            ;;
    esac
    if [[ "${resolved}" == "${repository_resolved}" \
        || "${resolved}" == "${repository_resolved}/"* \
        || "${repository_resolved}" == "${resolved}/"* ]]; then
        die 'Backup storage must not be the source repository, a child of it, or one of its parent directories.'
    fi
}

assert_no_placeholders() {
    local file="$1"
    if awk '$0 !~ /^[[:space:]]*#/ && $0 ~ /(CHANGE_ME|replace-me|example-password)/ { found = 1 } END { exit !found }' "${file}"; then
        die "${file} still contains a placeholder value."
    fi
}

compose_production() {
    docker compose --env-file "${ENV_FILE}" --file "${PRODUCTION_COMPOSE_FILE}" "$@"
}

check_production_configuration() {
    require_command docker
    docker info >/dev/null 2>&1 || die 'Docker Engine is not available.'
    docker compose version >/dev/null 2>&1 || die 'Docker Compose v2 is not available.'
    assert_no_placeholders "${ENV_FILE}"
    compose_production config --quiet
}

acquire_operation_lock() {
    local name="$1"
    if command -v flock >/dev/null 2>&1; then
        exec 9>"/tmp/mediqueue-${name}.lock"
        flock --nonblock 9 || die "Another ${name} operation is already running."
    fi
}
