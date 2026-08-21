# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG PYTHON_IMAGE=python:3.14.7-alpine3.23@sha256:6b8f06d04d5305c1d1288435388df9165ab41e681fae6439d6349d8053cc3f83
ARG ALPINE_IMAGE=alpine:3.23.5@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40

FROM ${PYTHON_IMAGE} AS python-runtime

FROM ${PYTHON_IMAGE} AS dependencies

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --requirement requirements.txt

FROM dependencies AS test-dependencies

COPY backend/requirements-dev.txt ./
RUN pip install --requirement requirements-dev.txt

FROM ${ALPINE_IMAGE} AS runtime

ARG APP_VERSION=unknown

ENV APP_VERSION=${APP_VERSION} \
    DJANGO_SETTINGS_MODULE=config.settings \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.title="MediQueue API" \
      org.opencontainers.image.description="Hospital operations API and notification worker" \
      org.opencontainers.image.revision=${APP_VERSION}

RUN apk add --no-cache \
        ca-certificates \
        gdbm \
        libbz2 \
        libcrypto3 \
        libffi \
        libncursesw \
        libpanelw \
        libssl3 \
        libuuid \
        readline \
        sqlite-libs \
        tzdata \
        xz-libs \
        zlib \
        zstd-libs \
    && addgroup --gid 10001 app \
    && adduser --uid 10001 --ingroup app --disabled-password --home /home/app app

WORKDIR /app
COPY --from=python-runtime /usr/local /usr/local
COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=app:app backend/ .

RUN rm -rf \
        /usr/local/bin/pip \
        /usr/local/bin/pip3 \
        /usr/local/bin/pip3.14 \
        /usr/local/lib/python3.14/site-packages/pip \
        /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
        /opt/venv/bin/pip \
        /opt/venv/bin/pip3 \
        /opt/venv/bin/pip3.14 \
        /opt/venv/lib/python3.14/site-packages/pip \
        /opt/venv/lib/python3.14/site-packages/pip-*.dist-info \
    && DJANGO_SECRET_KEY=build-only-django-key-used-only-for-static-assets-000000000000 \
    MFA_ENCRYPTION_KEY=build-only-mfa-key-used-only-for-static-assets-111111111111 \
    DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build \
    DJANGO_DEBUG=false \
    DJANGO_ALLOWED_HOSTS=localhost \
    DJANGO_SECURE_COOKIES=true \
    DJANGO_SECURE_SSL_REDIRECT=true \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=4s --start-period=30s --retries=4 \
    CMD python -c "import os, urllib.request; h=os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')[0]; r=urllib.request.Request('http://127.0.0.1:8000/api/v1/health/live/', headers={'Host':h, 'X-Forwarded-Proto':'https'}); urllib.request.urlopen(r, timeout=3)" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "--error-logfile", "-"]

FROM runtime AS test

COPY --from=test-dependencies /opt/venv /opt/venv

FROM runtime AS production
