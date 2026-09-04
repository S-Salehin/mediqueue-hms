# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG NODE_IMAGE=node:24.19.0-alpine@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43
ARG GO_IMAGE=golang:1.26.6-alpine3.23@sha256:5978cc992ad5ef96a7469713c8af849c1433824761ce3be2c56381403cd8d9a3
ARG ALPINE_IMAGE=alpine:3.23.5@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40

FROM ${NODE_IMAGE} AS dependencies

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM dependencies AS test

COPY frontend/ .
CMD ["npm", "run", "test:coverage"]

FROM dependencies AS build

ARG APP_VERSION=unknown
ENV VITE_APP_VERSION=${APP_VERSION}

COPY frontend/ .
RUN npm run build

FROM ${GO_IMAGE} AS caddy-build

ARG CADDY_VERSION=v2.11.4

WORKDIR /build
RUN go mod init mediqueue.invalid/caddy-build \
    && go mod download "github.com/caddyserver/caddy/v2@${CADDY_VERSION}" \
    && cp -a "/go/pkg/mod/github.com/caddyserver/caddy/v2@${CADDY_VERSION}" /src \
    && chmod -R u+w /src

WORKDIR /src
RUN go get \
        golang.org/x/net@v0.56.0 \
        golang.org/x/text@v0.39.0 \
        google.golang.org/grpc@v1.82.1 \
    && go mod tidy \
    && CGO_ENABLED=0 go build \
        -buildvcs=false \
        -trimpath \
        -ldflags="-s -w -X github.com/caddyserver/caddy/v2.CustomVersion=${CADDY_VERSION}+mediqueue.1" \
        -o /out/caddy \
        ./cmd/caddy \
    && /out/caddy version | grep -F "${CADDY_VERSION}+mediqueue.1"

FROM ${ALPINE_IMAGE} AS runtime

ARG APP_VERSION=unknown
LABEL org.opencontainers.image.title="MediQueue web" \
      org.opencontainers.image.description="Static hospital operations interface and same-origin reverse proxy" \
      org.opencontainers.image.revision=${APP_VERSION}

RUN apk add --no-cache ca-certificates mailcap tzdata \
    && addgroup -g 10002 web \
    && adduser -D -H -u 10002 -G web web \
    && mkdir -p /config /data /srv \
    && chown -R web:web /config /data /srv

COPY --from=caddy-build /out/caddy /usr/bin/caddy
COPY --from=build /app/dist /srv
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile

USER web
EXPOSE 8080 8443 8443/udp 8090

ENTRYPOINT ["/usr/bin/caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]

HEALTHCHECK --interval=15s --timeout=4s --start-period=10s --retries=4 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8090/healthz || exit 1
