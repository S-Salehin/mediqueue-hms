#!/usr/bin/env bash

set -Eeuo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${MEDIQUEUE_MIGRATION_USER:?MEDIQUEUE_MIGRATION_USER is required}"
: "${MEDIQUEUE_MIGRATION_PASSWORD:?MEDIQUEUE_MIGRATION_PASSWORD is required}"
: "${MEDIQUEUE_APP_USER:?MEDIQUEUE_APP_USER is required}"
: "${MEDIQUEUE_APP_PASSWORD:?MEDIQUEUE_APP_PASSWORD is required}"

if [[ "${POSTGRES_USER}" == "${MEDIQUEUE_MIGRATION_USER}" \
    || "${POSTGRES_USER}" == "${MEDIQUEUE_APP_USER}" \
    || "${MEDIQUEUE_MIGRATION_USER}" == "${MEDIQUEUE_APP_USER}" ]]; then
    printf 'Bootstrap, migration, and runtime database roles must be different.\n' >&2
    exit 1
fi

export PGPASSWORD="${POSTGRES_PASSWORD}"

psql --set=ON_ERROR_STOP=1 \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --set=migration_user="${MEDIQUEUE_MIGRATION_USER}" \
    --set=migration_password="${MEDIQUEUE_MIGRATION_PASSWORD}" \
    --set=app_user="${MEDIQUEUE_APP_USER}" \
    --set=app_password="${MEDIQUEUE_APP_PASSWORD}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'migration_user', :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'migration_user') \gexec

SELECT format('ALTER ROLE %I PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'migration_user', :'migration_password') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec

SELECT format('ALTER ROLE %I PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'app_user', :'app_password') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'migration_user') \gexec
SELECT format('ALTER SCHEMA public OWNER TO %I', :'migration_user') \gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'migration_user') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user') \gexec
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I', :'app_user') \gexec
SELECT format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'app_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', :'migration_user', :'app_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I', :'migration_user', :'app_user') \gexec
SQL
