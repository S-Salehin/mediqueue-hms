import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

// This is the quick read gate. The authenticated mixed staging workload in
// test.md is a separate release gate and includes write and integrity checks.

const baseUrl = (__ENV.BASE_URL || "http://web:8080").replace(/\/$/, "");
const targetEnvironment = (__ENV.TARGET_ENV || "test").toLowerCase();
const queueId = __ENV.QUEUE_ID || "";
const sessionCookie = __ENV.DJANGO_SESSION_COOKIE || "";
const requestErrors = new Rate("pilot_request_errors");

const targetMatch = baseUrl.match(/^https?:\/\/([^/:?#]+)/i);
if (!targetMatch) {
  throw new Error("BASE_URL must be an absolute HTTP or HTTPS origin.");
}
const targetHost = targetMatch[1].toLowerCase();
const localHosts = new Set(["127.0.0.1", "localhost", "web", "host.docker.internal"]);
const localRequestHeaders = targetHost === "web" ? { Host: "localhost" } : {};

if (targetEnvironment === "production") {
  const requiredApproval = `PRODUCTION:${targetHost}`;
  if (__ENV.LOAD_TEST_APPROVAL !== requiredApproval) {
    throw new Error(`Production load testing requires LOAD_TEST_APPROVAL=${requiredApproval}`);
  }
}

if (!localHosts.has(targetHost) && targetEnvironment !== "production") {
  const requiredApproval = `SYNTHETIC:${targetHost}`;
  if (targetEnvironment !== "staging" || __ENV.LOAD_TEST_APPROVAL !== requiredApproval) {
    throw new Error(`A remote synthetic target requires TARGET_ENV=staging and LOAD_TEST_APPROVAL=${requiredApproval}`);
  }
}

if ((queueId && !sessionCookie) || (!queueId && sessionCookie)) {
  throw new Error("QUEUE_ID and DJANGO_SESSION_COOKIE must be supplied together.");
}

export const options = {
  scenarios: {
    pilot_reads: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: __ENV.RAMP_DURATION || "15s", target: 50 },
        { duration: __ENV.HOLD_DURATION || "60s", target: 50 },
        { duration: __ENV.RAMP_DOWN_DURATION || "10s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    "http_req_duration{kind:read}": ["p(95)<500"],
    pilot_request_errors: ["rate<0.01"],
  },
  discardResponseBodies: true,
  userAgent: "MediQueue quick read load gate",
};

const publicPaths = [
  "/",
  "/api/v1/health/live/",
  "/api/v1/public/departments/",
  "/api/v1/health/ready/",
];

let queueEtag = "";

function record(response, label, acceptedStatuses = [200]) {
  const passed = check(response, {
    [`${label} returned an accepted status`]: (value) => acceptedStatuses.includes(value.status),
  });
  requestErrors.add(!passed);
}

export default function () {
  const requestNumber = (__VU * 13) + __ITER;
  const path = requestNumber % 30 === 0
    ? "/api/v1/public/doctors/"
    : publicPaths[requestNumber % publicPaths.length];
  const publicResponse = http.get(`${baseUrl}${path}`, {
    headers: localRequestHeaders,
    tags: { kind: "read", route: path },
    timeout: "10s",
  });
  record(publicResponse, path);

  if (queueId && (__ITER % 2 === 0)) {
    const headers = { ...localRequestHeaders, Cookie: sessionCookie };
    if (queueEtag) headers["If-None-Match"] = queueEtag;
    const queueResponse = http.get(`${baseUrl}/api/v1/queues/${queueId}/snapshot/`, {
      headers,
      tags: { kind: "read", route: "queue_snapshot" },
      timeout: "10s",
    });
    record(queueResponse, "queue snapshot", [200, 304]);
    if (queueResponse.status === 200 && queueResponse.headers.ETag) {
      queueEtag = queueResponse.headers.ETag;
    }
  }

  sleep(1);
}
