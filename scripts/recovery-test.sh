#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPOSITORY_ROOT}/.env.recovery.example"
COMPOSE_FILE="${REPOSITORY_ROOT}/compose.test.yml"
EXPECTED_PROJECT='mediqueue-recovery-test'
DOCKER_ENV_FILE="${ENV_FILE}"
DOCKER_COMPOSE_FILE="${COMPOSE_FILE}"

# Git Bash rewrites Linux container paths before they reach Docker. Give the
# Windows client native host paths, then disable rewriting for container paths.
if [[ -n "${MSYSTEM:-}" ]]; then
    DOCKER_ENV_FILE="$(cygpath --windows "${ENV_FILE}")"
    DOCKER_COMPOSE_FILE="$(cygpath --windows "${COMPOSE_FILE}")"
    export MSYS_NO_PATHCONV=1
fi

if [[ "${1:-}" != "--confirm" || "${2:-}" != "RECOVERY-TEST:${EXPECTED_PROJECT}" || $# -ne 2 ]]; then
    printf 'Usage: %s --confirm RECOVERY-TEST:%s\n' "$0" "${EXPECTED_PROJECT}" >&2
    exit 1
fi

command -v docker >/dev/null 2>&1 || { printf 'Docker is required.\n' >&2; exit 1; }
[[ -f "${ENV_FILE}" && -f "${COMPOSE_FILE}" ]] || { printf 'Recovery test configuration is missing.\n' >&2; exit 1; }
grep -Fqx "COMPOSE_PROJECT_NAME=${EXPECTED_PROJECT}" "${ENV_FILE}" \
    || { printf 'The recovery project name is not the expected isolated name.\n' >&2; exit 1; }

compose() {
    docker compose --env-file "${DOCKER_ENV_FILE}" --file "${DOCKER_COMPOSE_FILE}" --profile recovery "$@"
}

printf 'Starting the isolated PostgreSQL and pgBackRest services.\n'
compose up --build --detach --wait --wait-timeout 300 recovery-db recovery-backup

printf 'Writing a synthetic recovery marker.\n'
compose exec --no-TTY recovery-db psql \
    --username mediqueue_recovery_bootstrap \
    --dbname mediqueue_recovery_test \
    --set=ON_ERROR_STOP=1 \
    --command "CREATE TABLE recovery_marker (value text PRIMARY KEY); INSERT INTO recovery_marker VALUES ('synthetic-backup-restore-ok');"

printf 'Checking the nonroot database runtime and separated database roles.\n'
[[ "$(compose exec --no-TTY recovery-db id -u | tr -d '\r')" == '70' ]] \
    || { printf 'The recovery database is not running as uid 70.\n' >&2; exit 1; }
[[ "$(compose exec --no-TTY recovery-db awk '/^CapEff:/ {print $2}' /proc/1/status | tr -d '\r')" == '0000000000000000' ]] \
    || { printf 'The recovery database retained Linux capabilities.\n' >&2; exit 1; }
if compose exec --no-TTY recovery-db sh -c 'command -v gosu >/dev/null 2>&1'; then
    printf 'The recovery database unexpectedly contains gosu.\n' >&2
    exit 1
fi
if compose exec --no-TTY recovery-db sh -c 'touch /root-filesystem-write-probe'; then
    printf 'The recovery database root filesystem is writable.\n' >&2
    exit 1
fi
role_check="$(compose exec --no-TTY recovery-db psql \
    --username mediqueue_recovery_bootstrap \
    --dbname mediqueue_recovery_test \
    --tuples-only --no-align \
    --command "SELECT CASE WHEN
        owner_role.rolsuper = false AND owner_role.rolcreatedb = false AND owner_role.rolcreaterole = false
        AND owner_role.rolreplication = false AND owner_role.rolbypassrls = false
        AND runtime_role.rolsuper = false AND runtime_role.rolcreatedb = false AND runtime_role.rolcreaterole = false
        AND runtime_role.rolreplication = false AND runtime_role.rolbypassrls = false
        AND has_schema_privilege('mediqueue_recovery_runtime', 'public', 'USAGE')
        AND NOT has_schema_privilege('mediqueue_recovery_runtime', 'public', 'CREATE')
        THEN 'database-role-separation-ok' ELSE 'database-role-separation-failed' END
      FROM pg_roles owner_role CROSS JOIN pg_roles runtime_role
      WHERE owner_role.rolname = 'mediqueue_recovery_owner'
        AND runtime_role.rolname = 'mediqueue_recovery_runtime';" | tr -d '\r')"
[[ "${role_check}" == 'database-role-separation-ok' ]] \
    || { printf 'Database role separation did not match the approved policy.\n' >&2; exit 1; }

printf 'Creating and verifying an encrypted full backup.\n'
compose exec --no-TTY recovery-backup pgbackrest --stanza=mediqueue check
compose exec --no-TTY recovery-backup pgbackrest --stanza=mediqueue --type=full backup
compose exec --no-TTY recovery-backup pgbackrest --stanza=mediqueue verify

printf 'Stopping PostgreSQL before replacing only the isolated recovery data directory.\n'
compose stop recovery-db
compose run --rm --no-deps --entrypoint /bin/sh recovery-storage-init -c '
    target=/var/lib/postgresql/18/docker
    resolved="$(realpath "${target}")"
    [ "${resolved}" = "${target}" ] || { printf "Unexpected data path: %s\n" "${resolved}" >&2; exit 1; }
    find "${target}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
'

printf 'Restoring into the clean isolated data directory.\n'
compose run --rm --no-deps --user postgres --entrypoint pgbackrest recovery-db --stanza=mediqueue restore
compose up --detach --wait --wait-timeout 180 recovery-db

marker="$(compose exec --no-TTY recovery-db psql \
    --username mediqueue_recovery_bootstrap \
    --dbname mediqueue_recovery_test \
    --tuples-only --no-align \
    --command 'SELECT value FROM recovery_marker;')"
[[ "${marker}" == 'synthetic-backup-restore-ok' ]] \
    || { printf 'The recovery marker was not restored.\n' >&2; exit 1; }

printf 'Encrypted backup and clean restore passed. Removing only %s resources.\n' "${EXPECTED_PROJECT}"
compose down --volumes --remove-orphans
