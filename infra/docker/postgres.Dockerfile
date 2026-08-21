# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG POSTGRES_IMAGE=postgres:18.6-alpine3.23@sha256:f65cfc1a73466fc0807f4a33496e1c438b19269091c8f998faec871874df8e5e
ARG PGBACKREST_VERSION=2.59.0
# The upstream distribution asset includes generated sources that are absent
# from GitHub's automatic tag archive. This checksum is published with it.
ARG PGBACKREST_SHA256=faaf8faa14a6392279654ee216a493fcd07b0c513af4b55fe34faec062cb8875
ARG APP_VERSION=unknown

FROM ${POSTGRES_IMAGE} AS pgbackrest-build

ARG PGBACKREST_VERSION
ARG PGBACKREST_SHA256

RUN apk add --no-cache \
        build-base \
        ca-certificates \
        curl \
        curl-dev \
        bzip2-dev \
        lz4-dev \
        postgresql-dev \
        libssh2-dev \
        openssl-dev \
        libxml2-dev \
        yaml-dev \
        zstd-dev \
        meson \
        samurai \
        pkgconf

RUN curl --fail --location --silent --show-error \
        "https://github.com/pgbackrest/pgbackrest/releases/download/release/${PGBACKREST_VERSION}/pgbackrest-${PGBACKREST_VERSION}.tar.gz" \
        --output /tmp/pgbackrest.tar.gz \
    && echo "${PGBACKREST_SHA256}  /tmp/pgbackrest.tar.gz" | sha256sum -c - \
    && mkdir /tmp/pgbackrest \
    && tar --extract --gzip --file /tmp/pgbackrest.tar.gz --directory /tmp/pgbackrest --strip-components=1

RUN meson setup /tmp/pgbackrest-build /tmp/pgbackrest \
    && samu -C /tmp/pgbackrest-build

FROM ${POSTGRES_IMAGE} AS runtime

ARG PGBACKREST_VERSION
ARG APP_VERSION

LABEL org.opencontainers.image.title="MediQueue PostgreSQL" \
      org.opencontainers.image.description="PostgreSQL 18 with checksum verified pgBackRest" \
      org.opencontainers.image.revision=${APP_VERSION} \
      org.opencontainers.image.version.pgbackrest=${PGBACKREST_VERSION}

RUN apk add --no-cache \
        libbz2 \
        lz4-libs \
        libpq \
        libssh2 \
        libssl3 \
        libxml2 \
        yaml \
        zstd-libs \
    && rm -f /usr/local/bin/gosu \
    && mkdir -p /etc/pgbackrest /var/lib/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest \
    && chown --recursive postgres:postgres /var/lib/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest

COPY --from=pgbackrest-build /tmp/pgbackrest-build/src/pgbackrest /usr/local/bin/pgbackrest
COPY infra/backup/pgbackrest.conf /etc/pgbackrest/pgbackrest.conf
COPY --chmod=0755 infra/postgres/init/10-create-application-role.sh /docker-entrypoint-initdb.d/10-create-application-role.sh

RUN chmod 0755 /usr/local/bin/pgbackrest \
    && chmod 0640 /etc/pgbackrest/pgbackrest.conf \
    && chown postgres:postgres /etc/pgbackrest/pgbackrest.conf \
    && pgbackrest version | grep -F "pgBackRest ${PGBACKREST_VERSION}"

USER postgres
