# Verification and Acceptance Plan

Document status: Production candidate baseline

Last reviewed: 14 August 2026

System codename: MediQueue

## 1. Purpose

This document defines the evidence required to accept the hospital operations and adaptive queue system. It covers automated tests, manual verification, hospital user acceptance, security review, performance, backup restoration, and deployment safety.

Passing a demonstration is not enough. The release is accepted only when its critical workflows, permissions, transaction controls, recovery process, and privacy boundaries work under realistic conditions.

## 2. Quality objectives

The test programme must prove the following outcomes.

1. A patient can register, verify an account, find a doctor, book an available appointment, view only personal records, and follow a privacy safe queue token.
2. Reception can register or locate a patient, avoid accidental duplicates, book or reschedule, check in, create a walk in, manage the queue, and record an onsite payment without creating duplicate business events.
3. A doctor can operate only the assigned schedule and queue and can see only the minimum patient identity information required for those appointments.
4. An administrator can manage configuration and review audit evidence without gaining a hidden path that bypasses normal controls.
5. Concurrent requests cannot overbook a slot, issue duplicate queue tickets, call two patients at once, or duplicate a payment.
6. The adaptive arrival estimate is deterministic, bounded, clearly labelled, and never used for medical triage or patient priority.
7. Failure of email, polling, a browser connection, or a worker does not corrupt the underlying appointment or queue action.
8. The application meets the defined accessibility, security, performance, backup, and recovery acceptance levels.

## 3. Test ownership and evidence

The developer who implements a change writes its unit and integration tests. A second reviewer checks security boundaries, state transitions, failure handling, and test usefulness. The release owner collects the final evidence. Hospital representatives perform user acceptance rather than relying on developer demonstrations.

Every failed test creates a reproducible record containing environment, release identifier, test data, exact action, expected result, actual result, supporting log or screenshot, severity, owner, and regression test requirement. Patient names, working credentials, session values, and production data must not appear in test evidence.

The retained release evidence includes:

1. Backend, frontend, and browser test reports.
2. Coverage reports and the list of explicitly tested permission and transition paths.
3. Dependency, container, secret, static analysis, and dynamic security scan results.
4. Accessibility automated results and manual check sheets.
5. Load test script, dataset version, raw summary, and percentile report.
6. Backup restore and rollback exercise records.
7. Doctor, receptionist, administrator, and patient acceptance records.
8. Approved exceptions with owner, control, and expiry date.

## 4. Test environments and data

### 4.1 Local and continuous integration

Automated backend tests run against PostgreSQL 18. Tests that exercise row locks or competing transactions must use separate database connections and real committed transactions. SQLite is prohibited for all acceptance evidence.

Frontend unit tests use a browser compatible DOM environment. End to end tests run against a built frontend and the real Django API. Network calls are not mocked in release browser tests except when a test intentionally simulates email or network failure.

### 4.2 Staging

Staging matches production versions, reverse proxy routes, TLS behaviour, database configuration, worker process, security headers, and timezone behaviour. Security, load, restoration, and hospital acceptance tests run in staging or an isolated copy of it. Destructive tests never run against production.

### 4.3 Synthetic dataset

The standard dataset contains 30 doctors across realistic departments and locations, at least 500 appointments on a busy day, schedule closures, full and partially full slots, cancelled and completed appointments, active and completed queue sessions, payment states, notification retries, and audit events.

Generated people use unmistakably synthetic names, reserved email domains, and nonroutable phone values accepted only in test settings. No copied patient record, live email address, national identifier, real prescription, or clinical text is allowed.

Time dependent tests freeze the application clock. They include UTC storage, Asia/Dhaka display, midnight boundaries, month and year boundaries, leap day, and a server clock close to a slot or cancellation cutoff. Tests must not depend on the workstation timezone.

## 5. Automated test layers

### 5.1 Backend unit tests

Unit tests cover model constraints, services, validators, permission policies, state transition rules, medical record number generation, slot calculation, wait estimation, notification rendering, retry timing, audit event creation, and error conversion.

The tests assert results and persisted side effects. A test that only checks an HTTP success status is incomplete when a database record, audit event, notification, or state history should also exist.

### 5.2 Backend API tests

API tests use the same middleware, session authentication, CSRF rules, serializers, view permissions, transaction services, and PostgreSQL constraints used in production. They cover success, validation failure, permission denial, missing object, conflict, repeated request, stale state, and unexpected service failure.

### 5.3 Frontend unit and integration tests

Frontend tests cover route guards, session expiry, forms, error summaries, slot selection, state labels, queue freshness, conditional polling, notification status, responsive navigation, accessible dialogs, and retry controls.

Tests use user level interactions such as typing, tabbing, clicking, and submitting. Assertions should target visible roles, names, state, and outcomes rather than private component structure.

### 5.4 Browser workflow tests

Playwright tests exercise the built frontend and real Django API through the same origin disposable stack. The automated release suite uses the exact pinned Playwright Chromium version and covers the public service, patient availability, staff MFA, receptionist check in, the patient queue projection, and the assigned doctor queue. Current Firefox, WebKit, Edge, Android Chrome, and mobile Safari checks remain a staging sign off gate before real patient data is allowed. A reduced Chromium smoke set runs after deployment with synthetic release records.

## 6. Identity and session tests

### 6.1 Patient identity

1. Registration rejects invalid or duplicate account credentials without revealing whether an unrelated patient profile exists.
2. A patient account remains unverified until the single use email link succeeds.
3. An expired, altered, or reused verification link fails and records no consent or verified state.
4. A receptionist can create an unclaimed patient profile without an email address and receives a generated unique medical record number.
5. Claiming an existing profile requires the approved identity check. A matching name or phone number alone is not sufficient.
6. Password reset returns the same public response for existing and unknown addresses.
7. Changing a password invalidates other active sessions according to the documented session policy.

### 6.2 Staff identity

1. Public staff registration does not exist.
2. A staff invitation is single use, expires, is bound to the intended role, and cannot create a more privileged role.
3. A doctor, receptionist, or administrator cannot access protected work until time based one time password enrolment and confirmation are complete.
4. Valid and invalid one time passwords, replay, clock tolerance, backup recovery, and disabled device behaviour are tested.
5. Repeated failed sign in attempts trigger the configured rate limit or lockout and create a security event without logging the attempted password.
6. Deactivated staff lose access at the next request and cannot restore access through an older session.

### 6.3 Session and CSRF controls

1. Authentication uses an HttpOnly, Secure production cookie with the approved SameSite policy.
2. No access token, refresh token, password, or patient profile is stored in browser local storage.
3. Every state changing browser request without a valid CSRF token fails.
4. A token from another session, an expired token, and a token sent from an untrusted origin fail.
5. Session expiry returns the stable authentication error and the frontend preserves no sensitive screen state after redirecting to sign in.
6. Logout invalidates the server session and a repeated logout remains safe.

## 7. Permission and privacy matrix

Permission tests create at least two users in every role, two doctors, two departments, and records owned by different people. Every object endpoint is tested with the owner, another user of the same role, each other role, an unauthenticated session, a deactivated account, and an altered UUID.

### 7.1 Patient permissions

1. A patient can read and change only the permitted fields of the personal profile.
2. A patient can list, view, cancel, or reschedule only personal appointments.
3. A patient can read only personal queue tickets and notifications.
4. Queue responses never reveal another patient’s name, medical record number, contact details, appointment identifier, or reason for visit.
5. A patient cannot use list filters, search, exports, guessed UUIDs, nested routes, or error differences to discover another patient.

### 7.2 Doctor permissions

1. A doctor sees the assigned schedules and today’s assigned queue only.
2. A doctor sees the minimum identity fields for patients attached to those appointments.
3. A doctor cannot open another doctor’s appointment or queue by changing a path, body identifier, filter, or location.
4. A doctor cannot manage hospital configuration, staff roles, payment records, or unrestricted audit records.

### 7.3 Receptionist permissions

1. A receptionist may search patients using the approved fields, create a patient, manage bookings, check in, create walk ins, operate the queue, and record onsite payments.
2. Search results disclose only the minimum fields needed to distinguish likely matches.
3. Reception cannot manage staff roles, change security configuration, erase audit history, or access data outside the hospital boundary.
4. Sensitive corrections and queue overrides require a reason and create an audit event.

### 7.4 Administrator permissions

1. An administrator can manage departments, locations, doctors, schedules, staff invitations, configuration, and permitted reports.
2. An administrator cannot silently change a completed business event or delete immutable audit history.
3. Audit access and exports are themselves audited.
4. A role change takes effect immediately and cannot be achieved through an unapproved request field.

The permission section passes only when every denial produces no protected content and no unauthorised side effect. A hidden interface control is not evidence of API authorisation.

## 8. Hospital configuration and scheduling tests

1. Departments, locations, and doctor profiles require their defined fields and reject inactive or cross hospital relationships.
2. A schedule rejects an end time before its start, a zero or negative duration, invalid capacity, and overlapping rules for the same doctor and location.
3. Availability is generated for the correct local day, slot duration, capacity, location, doctor, and approved date range.
4. A closure removes the affected availability without deleting existing appointment history.
5. A partial exception changes only the stated period and leaves other schedule instances unchanged.
6. Inactive doctors, departments, or locations do not accept new appointments but remain visible in authorised historical records.
7. Existing bookings behave according to the approved closure workflow and produce clear staff action rather than silent cancellation.
8. Capacity is calculated from committed active appointments, not a cached browser count.

## 9. Patient registration and duplicate control tests

1. Medical record numbers are unique under sequential and concurrent profile creation.
2. A generated medical record number is never reused after deactivation or correction.
3. Required name, date of birth, contact, address, sex or gender fields, and consent fields follow the approved validation and optionality rules.
4. Phone numbers are stored in E.164 form and displayed in the approved local format.
5. Duplicate checks detect the approved strong and possible match combinations and return a warning rather than merging automatically.
6. An authorised receptionist may continue after a possible match only with a recorded reason.
7. Correction preserves the original audit evidence. Deactivation does not cascade delete appointments, queues, payments, consent, or audit events.

## 10. Appointment tests

### 10.1 Booking

1. A patient or receptionist can book an open slot with remaining capacity.
2. Booking an inactive doctor, closed schedule, past slot, invalid location, or full capacity returns a conflict or validation error and creates no appointment.
3. A successful booking creates one confirmed appointment, one initial state history record, one audit event, and the required notification outbox item in the same transaction.
4. An email delivery failure does not undo a committed appointment.
5. Repeating the same request with the same `Idempotency-Key` returns the original outcome and creates no duplicate record.
6. Reusing an idempotency key with a different payload returns a conflict.
7. Two patients competing for the last capacity position result in exactly one success and one conflict.

### 10.2 Rescheduling and cancellation

1. Rescheduling locks the appointment and target capacity, preserves history, frees the old capacity, and consumes the new capacity atomically.
2. Two reschedules competing for the last target position result in one success without losing either original appointment.
3. Cancellation changes a confirmed appointment once, records actor and time, creates the notification and audit event, and releases capacity.
4. Repeated cancellation is idempotent and does not duplicate history or notification.
5. Cancelled, completed, and no show appointments reject illegal actions with a stable conflict error.
6. Patient cancellation or rescheduling respects the configured time rule. Authorised staff override records its reason.

### 10.3 State transitions

The transition suite enumerates every source and target combination for `confirmed`, `cancelled`, `completed`, and `no_show`. Every allowed transition asserts history and audit side effects. Every forbidden transition asserts no persisted change.

## 11. Reception and check in tests

1. Reception can locate today’s confirmed appointment and verify the intended patient with the approved identity fields.
2. Check in creates one queue ticket and final token only when the appointment and queue session are eligible.
3. Simultaneous check in requests for one appointment return one ticket.
4. Simultaneous check ins for different patients produce distinct, ordered tokens without a gap caused by a failed transaction.
5. A cancelled, completed, wrong day, wrong doctor, or already checked in appointment cannot receive another ticket.
6. A walk in creates the patient link, appointment, queue ticket, histories, audit event, and notification atomically.
7. Late arrival follows the documented staff decision and never changes priority silently.
8. An identity or booking correction records the original value, corrected value, actor, time, and reason where policy requires it.

## 12. Queue state and fairness tests

The queue transition suite enumerates `waiting`, `called`, `in_service`, `deferred`, `completed`, `no_show`, and `cancelled` states.

1. Calling next selects the earliest eligible check in using first in, first out order.
2. Two staff members calling next at the same time result in one active called ticket and one consistent second response.
3. Starting service is permitted only for the called ticket assigned to that queue session.
4. Completing service records valid start and end times, updates the appointment, and contributes one valid duration to later estimates.
5. Defer, restore, reinsert, no show, cancellation, and operational override require an authorised role and reason.
6. Each queue action records actor, UTC time, previous state, new state, queue position evidence, and reason where required.
7. A deferred patient does not disappear. Restoration follows the documented fairness rule and is visible in the audit history.
8. A no show can be corrected only through the approved transition and reason. The original event remains recorded.
9. No endpoint accepts a symptom, diagnosis, severity, or clinical priority value that changes queue order.
10. A patient snapshot includes only personal token, currently served token, wait range, recommended return window, confidence label, and last updated time.

## 13. Adaptive arrival calculation tests

The calculation uses deterministic fixtures and a frozen time.

1. With fewer than five valid completed visits for the doctor, the configured schedule duration is the service estimate.
2. From five valid visits onward, the observed component is the median of no more than the latest 20 valid completed service durations.
3. The estimate equals 70 percent of that median plus 30 percent of the configured duration.
4. The final service estimate is clamped to a minimum of 5 minutes and a maximum of 60 minutes.
5. Cancelled, no show, missing start, missing end, negative, zero, and otherwise invalid durations are excluded.
6. Exactly 20 and more than 20 valid samples prove that only the latest 20 are used.
7. Odd and even sample counts prove correct median handling.
8. Sufficient valid samples use the documented median absolute deviation range. Sparse samples use the wider fallback range and lower confidence label.
9. The number of eligible people ahead, active service state, and current time produce the expected wait range and return window.
10. A wait range never has a negative lower bound, reversed endpoints, or a recommendation in the past.
11. Recalculation never changes token order or creates a clinical priority.
12. Staff overrides do not rewrite historical estimates and always record a reason.

After pilot data exists, the operational report measures absolute error, median absolute error, interval coverage, override rate, stale snapshot rate, and sample count by doctor. These are quality observations, not claims of medical accuracy.

## 14. Queue polling and cache validation tests

1. A queue snapshot response contains an ETag derived from authorised visible state.
2. A matching `If-None-Match` returns 304 with no response body or protected data.
3. An ETag for one patient cannot validate or reveal another patient’s snapshot.
4. A visible active page polls every 10 seconds. A background page polls every 30 seconds.
5. The interface shows stale status after 30 seconds without a successful update.
6. Going offline stops request storms, retains the last update time, and clearly marks the data stale.
7. Reconnection requests a fresh snapshot and removes stale status only after success.
8. Polling stops after logout, ticket completion, route exit, or component removal.
9. Slow responses do not create overlapping requests or apply an older snapshot after a newer one.
10. Server errors use bounded retry behaviour and never expose raw exception text.

## 15. Payment record tests

1. The system accepts integer BDT minor units and rejects negative, fractional minor unit, unsupported currency, or out of range values.
2. Permitted states are `unpaid`, `paid_on_site`, `waived`, and `refunded`.
3. Every allowed transition records amount, actor, time, approved payment method description, and audit event.
4. Duplicate submission with the same idempotency key creates one payment event.
5. An appointment cannot receive conflicting successful onsite payments under concurrent requests.
6. A refund or waiver requires the permitted role and reason.
7. No interface or API accepts, stores, logs, or displays a card number, security code, magnetic stripe value, mobile wallet secret, or banking credential.
8. Payment corrections preserve earlier records rather than overwriting financial history.

## 16. Notification and outbox tests

1. Appointment and queue business actions commit their outbox items in the same database transaction.
2. Rolling back the business transaction leaves no sendable notification.
3. The worker locks one item safely so two workers cannot send the same attempt concurrently.
4. Temporary SMTP failure increments attempt data and retries with the configured bounded delay.
5. Permanent failure records its final state, raises the operational signal, and leaves the appointment or queue event intact.
6. A crashed worker can resume an abandoned item safely.
7. Patient preferences are respected except for an approved essential operational message.
8. An in application notification is visible only to its recipient and records read state once.
9. Email subject and body contain no symptom, diagnosis, specialty, other patient identity, or exposed queue details.
10. Links use the approved HTTPS origin and lead to authentication before protected information is displayed.
11. Template output escapes user controlled content and has a readable plain text alternative.

## 17. Consent and audit tests

1. Registration records the exact privacy notice version, consent choice, actor, and UTC time.
2. A later notice version does not alter earlier consent evidence.
3. Required consent cannot be inferred from a preselected browser control.
4. Withdrawal or correction follows the approved policy and preserves historical evidence.
5. Appointment, queue, payment, consent, staff access, configuration, and administrative changes create the required audit events.
6. Audit events are append only through the application. Ordinary roles cannot update or delete them.
7. Audit details contain identifiers and changed fields needed for investigation but exclude secrets, email bodies, raw request bodies, and unnecessary patient information.
8. Audit search is permission controlled, bounded, and audited.
9. Failed privileged actions and repeated authentication failures create the approved security evidence without recording attempted credentials.

## 18. API contract tests

1. Versioned routes remain under `/api/v1/`.
2. JSON errors use `status`, `code`, `title`, `detail`, `field_errors`, and `request_id` consistently.
3. Validation errors associate messages with the correct fields and provide a usable general detail.
4. Permission denial does not reveal whether a protected object exists.
5. Unsupported media type, malformed JSON, excessive body size, unknown field, invalid UUID, missing CSRF, rate limit, and internal error return the documented status and code.
6. Every response has a request identifier that matches the sanitised server log record.
7. External write endpoints enforce `Idempotency-Key` according to the documented retention and payload matching rules.
8. List endpoints enforce pagination, safe ordering, allowed filters, result limits, and role filtered querysets.
9. Dates and times use the documented ISO 8601 representation with an offset or UTC marker.
10. Security headers, content type, cache control, and origin behaviour match the deployment policy.

Contract fixtures are version controlled. An intentional incompatible contract requires a new API version or a documented migration accepted before release.

## 19. Concurrency and integrity tests

Concurrency tests use barriers to release separate PostgreSQL connections at the same point. They run repeatedly to expose timing dependent failures and inspect final database state, not only response codes.

1. At least 20 attempts compete for the final appointment capacity. Exactly one available capacity is consumed.
2. At least 20 check in attempts target one appointment. Exactly one queue ticket and token exist.
3. Ten eligible patients check in concurrently. All receive unique sequential tokens and valid histories.
4. Two staff members call next concurrently. Only one ticket becomes called for the same queue position.
5. Completion and defer compete for one ticket. One legal final transition wins and the loser receives a conflict.
6. Reschedule and cancellation compete for one appointment. The result follows one complete legal transaction without lost capacity.
7. Duplicate onsite payment requests create one financial event.
8. Two workers claim the same outbox pool without sending one item twice in the same attempt.
9. Concurrent patient creation cannot duplicate a medical record number.
10. A failed transaction releases locks, leaves no partial history or audit record, and allows a later valid request.

Database constraint tests also attempt invalid records directly through model and service boundaries to prove that essential invariants do not rely only on frontend validation.

## 20. Accessibility tests

The target is WCAG 2.2 Level AA for the public directory, authentication, patient booking, patient queue, receptionist workspace, doctor queue, and administrator configuration used in the pilot.

### 20.1 Automated checks

Automated axe checks run on each important page in default, empty, loading, validation error, server error, success, stale queue, and dialog states. Acceptance requires no critical or serious axe finding. Color contrast is also checked from the final computed styles.

### 20.2 Manual keyboard checks

1. Every action is reachable and operable with keyboard only.
2. Focus order follows the visible reading order and never enters hidden content.
3. Focus is visible, is restored when a dialog closes, and moves to a useful location after navigation or submitted errors.
4. There is no keyboard trap. Escape behaviour is predictable where dismissal is safe.
5. Skip navigation reaches the main content.
6. Date, time, slot, queue, and menu controls work without pointer gestures.

### 20.3 Screen reader checks

Core workflows are tested with NVDA and a current Chromium browser. Public and patient workflows receive an additional check with a current mobile screen reader.

1. Pages have one useful primary heading and descriptive titles.
2. Fields have persistent names, instructions, required state, and linked error messages.
3. Error summaries announce once and link to invalid fields.
4. Status is not communicated by color alone.
5. Queue changes announce useful personal status without repeatedly reading the whole page or another patient’s information.
6. Tables, lists, dialogs, navigation, and live regions expose correct names and relationships.

### 20.4 Visual and responsive checks

Normal text meets a 4.5 to 1 contrast ratio. Large text and meaningful interface graphics meet 3 to 1. Content remains usable at 200 percent browser zoom and 400 percent text reflow without loss of action or horizontal scrolling for ordinary page content.

Pages are manually checked at 320, 375, 768, 1024, and 1440 CSS pixel widths. Touch targets, error text, focus, dialogs, tables, and navigation remain usable. Reduced motion settings remove nonessential animation.

## 21. Security verification

Security verification follows the controls applicable to an OWASP Application Security Verification Standard 5.0 Level 2 web application. The team maintains a control checklist linking each applicable requirement to a test, code review, deployment setting, or accepted exclusion.

### 21.1 Automated security checks

1. Secret scanning covers Git history and the release workspace.
2. Python and JavaScript dependency audits use the locked dependency graphs.
3. Static analysis checks Python, JavaScript, Docker, workflow, and infrastructure files.
4. The final container image is scanned for operating system and application vulnerabilities.
5. A baseline dynamic scan runs against staging. Authenticated scans use dedicated synthetic accounts and approved rate limits.
6. Django deployment checks run with production settings.

The release has no unresolved critical or high finding. A medium finding requires documented reachability, control, owner, due date, and approval. Scanner output is reviewed for false positives rather than accepted or dismissed automatically.

### 21.2 Manual security scenarios

1. Object identifiers are altered across every role to test broken object level authorisation.
2. Role, ownership, hospital, state, amount, and audit fields are added to request bodies to test mass assignment.
3. Stored and reflected script payloads are tested in names, search, configuration, and notification templates.
4. SQL metacharacters and malformed filters are tested without relying on error hiding.
5. Cross site request forgery, hostile Origin and Referer values, clickjacking, content sniffing, and insecure HTTP behaviour are tested.
6. Sign in, verification, reset, invitation, MFA, patient search, booking, and queue actions are tested for rate limiting and account enumeration.
7. Session fixation, session reuse after logout, privilege change, concurrent device handling, and cookie scope are tested.
8. Cache headers are checked to prevent shared caching of patient and staff responses.
9. Logs, error monitoring, emails, URLs, browser storage, source maps, and health endpoints are inspected for personal data and secrets.
10. File path traversal, unsafe redirects, server side request forgery surfaces, and command execution surfaces are reviewed even where no file upload exists.

Production penetration testing, if commissioned, requires a written scope, test window, source addresses, emergency contact, and data handling agreement. It never uses real patient records.

## 22. Performance and load tests

Load tests run on staging sized like production with production debug settings disabled. Monitoring confirms whether response time comes from the API, database, worker, or host. Test data is reset through an approved staging procedure after the run.

### 22.1 Quick local read gate

The Compose `load-test` service is a short feedback check, not the release workload. It ramps to 50 virtual users, holds for 60 seconds, and tests the application shell, health endpoints, public directory reads, and an optional authenticated queue snapshot. Its only performance threshold is read p95 below 500 milliseconds. It also rejects an unapproved production target, an unapproved remote staging target, and incomplete queue credentials.

A passing quick gate proves that the assembled local proxy and read paths remain responsive under that narrow workload. It does not measure write latency, booking or queue integrity, notification recovery, sustained host behaviour, or production capacity. Its result must never be reported as the full load release gate.

### 22.2 Required staging workload

The dataset contains 30 doctors, 500 appointments for the busy day, at least 10,000 historical completed visits for estimate queries, and representative audit and notification history.

The test ramps from 1 to 50 concurrent users over five minutes, maintains 50 for 30 minutes, and ramps down over five minutes. The traffic mix includes public directory and availability reads, patient dashboard reads, queue snapshots with conditional requests, patient booking actions, receptionist search and check in, doctor queue actions, and administrator reads. Write workflows use independent records so expected conflicts are distinguishable from failures.

### 22.3 Staging pass conditions

1. The 95th percentile is below 500 milliseconds for read requests.
2. The 95th percentile is below 800 milliseconds for write requests.
3. Unexpected request failure rate is below 1 percent.
4. Queue data visible to a connected client is no more than 15 seconds behind the committed event.
5. No appointment exceeds capacity, no token duplicates, no illegal queue state appears, and no outbox item is lost.
6. Database connections remain within the configured safe pool and no sustained lock queue remains after load ends.
7. Host memory does not grow continuously, disk does not fill, and no container restarts because of resource exhaustion.
8. The notification worker returns to a pending age below two minutes within five minutes after the load ends.

A separate spike run moves from 10 to 50 users within 30 seconds and holds for five minutes. The system may become slower, but it must not corrupt data, exceed a 2 percent unexpected error rate, or fail to recover within five minutes after the spike.

## 23. Reliability and failure tests

1. Stop the worker while bookings continue. Business actions succeed, outbox age alerts, and the restarted worker drains each item safely.
2. Block SMTP temporarily. Retries follow policy and no appointment or queue transaction rolls back.
3. Restart the API during active polling. Clients mark data stale, recover, and do not submit a duplicate action.
4. Restart PostgreSQL in staging. Readiness fails, writes return a controlled error, services reconnect, and no partial transaction remains.
5. Fill a controlled test volume to the warning and critical thresholds. Alerts arrive before database safety is threatened.
6. Expire or replace the TLS certificate in an isolated environment and verify monitoring and client failure behaviour.
7. Introduce a poison outbox item. It reaches a bounded permanent failure state without blocking later valid items.
8. Simulate a process exit after acquiring an idempotency record and prove a later retry reaches a defined result.
9. Interrupt a deployment between migration and service replacement. The operator can identify the schema state and resume or roll back safely.

## 24. Backup, restore, and disaster recovery tests

A release cannot accept real data until a clean restore exercise has passed.

1. Create known records across users, roles, schedules, appointments, state history, queue tickets, queue events, payments, notifications, consent, and audit events.
2. Complete a full encrypted backup, at least one hourly recovery point, and archived write ahead logs.
3. Add a second known transaction after the full backup and record its exact commit time.
4. Provision a clean isolated PostgreSQL 18 volume and restore to the selected point.
5. Verify migration state, database consistency, row counts, foreign key relationships, uniqueness constraints, sampled values, state history order, and audit continuity.
6. Start the matching application image and complete login, booking, check in, queue, payment, notification preview, and audit search smoke tests without external delivery.
7. Measure the newest restored transaction and time to usable service.
8. Confirm a data gap no greater than one hour and usable recovery within four hours.
9. Confirm the restored environment cannot send production email and is securely removed after evidence collection.
10. Repeat restoration monthly and after a PostgreSQL major version, backup tool, encryption, or storage provider change.

A separate rollback exercise deploys a safe test release, applies its migration, returns to the recorded previous image and compatible schema, and verifies critical workflows. A release with an irreversible migration must instead rehearse the documented forward repair or full restore path.

## 25. Deployment smoke tests

The staging smoke test runs after every release deployment. The production smoke test uses only dedicated synthetic accounts and records.

1. Public HTTPS redirects and security headers are correct.
2. Liveness and readiness behave correctly and expose no sensitive data.
3. Patient sign in, staff sign in with MFA, session refresh, and logout work.
4. The public doctor directory and availability return expected data.
5. A synthetic patient books one open test slot.
6. Reception locates that record and checks it in once.
7. The doctor calls, starts, and completes the synthetic queue ticket.
8. The patient snapshot reveals no other patient identity and updates within 15 seconds.
9. The onsite payment test records the approved synthetic amount once.
10. Notification outbox, worker result, state history, and audit events are present.
11. Monitoring receives the expected healthy signals and no new critical alert appears.

Production synthetic records use an explicit release test marker and are removed only through the approved test cleanup service so their audit evidence remains understandable.

## 26. Hospital user acceptance

User acceptance occurs in staging with hospital approved synthetic scenarios. The facilitator observes and records outcomes but does not take over the user’s actions.

### 26.1 Patient representative

The representative registers, verifies email, signs in, finds a doctor, understands availability, books, reschedules, cancels, reviews a notification, follows a queue token, recognises stale data, and signs out. The representative must be able to identify the current token and wait range without seeing another patient’s identity.

### 26.2 Receptionist representative

The receptionist finds an existing patient, handles a duplicate warning, creates an unclaimed profile, books, creates a walk in, checks in, corrects a mistake, defers and restores a ticket with a reason, records an onsite payment, handles email failure, uses the downtime form, and reconciles the synthetic event after recovery.

### 26.3 Doctor representative

The doctor signs in with MFA, views the assigned schedule, opens today’s queue, calls next, starts service, completes service, records a no show, corrects a permitted mistake, and confirms that another doctor’s queue is unavailable.

### 26.4 Administrator representative

The administrator creates a department and location, invites staff, configures a schedule and closure, deactivates a staff account, reviews an audited override, checks operational status, and confirms that immutable history cannot be silently edited.

### 26.5 Acceptance condition

Each critical scenario requires the representative’s expected outcome, observed outcome, result, comments, and signature. All critical scenarios must pass. A failed critical scenario is corrected and repeated from its initial state. Verbal approval without the signed record is not release evidence.

## 27. Coverage and continuous integration gates

Backend domain and API line coverage must be at least 85 percent. Frontend logic line coverage must be at least 75 percent. Coverage does not replace meaningful assertions.

Regardless of percentage, every permission decision, appointment transition, queue transition, payment transition, transaction conflict, idempotency path, audit event, and adaptive estimate boundary requires an explicit test.

Every pull request must pass:

1. Backend unit, API, migration, and constraint tests.
2. Frontend unit and integration tests.
3. Critical browser workflow tests.
4. Formatting and static analysis checks that do not rewrite the release workspace.
5. Secret, dependency, and source security scans.
6. Frontend production build and application container build.
7. Coverage thresholds and changed contract checks.

The protected main branch does not accept a bypassed failed check. An infrastructure failure may be rerun, but it may not be relabelled as a passing product test.

## 28. Defect severity and release rules

1. Severity 1 is a credible personal data exposure, unauthorised privilege, lost or corrupted business record, unsafe queue behaviour, backup failure with no valid recovery point, or complete critical workflow failure. Release is blocked.
2. Severity 2 is a broken critical workflow with no safe practical workaround, repeated duplicate event, material accessibility barrier, or service objective failure at expected load. Release is blocked.
3. Severity 3 is a limited defect with a documented safe workaround and no material privacy, integrity, accessibility, or operational risk. Release requires an owner and due date.
4. Severity 4 is cosmetic or documentary and does not mislead a user. It may enter the normal backlog.

A flaky test is treated as a defect. It is fixed or removed with a documented replacement that preserves coverage. Repeated reruns until green are not acceptable evidence.

## 29. Final release acceptance

The production candidate is accepted only when all of these statements are true.

1. All automated required suites pass from a clean checkout and empty PostgreSQL database.
2. Coverage meets the thresholds and all critical paths have explicit tests.
3. Permission, concurrency, state transition, and privacy suites pass without exception.
4. Accessibility has no critical or serious automated finding and all critical manual workflows pass.
5. Security review has no unresolved critical or high finding.
6. The expected load profile meets response, error, integrity, and freshness conditions.
7. Backup restoration meets the one hour recovery point and four hour recovery time objectives.
8. Staging deployment, rollback rehearsal, production configuration check, and smoke tests pass.
9. Doctor and receptionist representatives sign every critical workflow. Patient and administrator acceptance is recorded.
10. Monitoring and alert delivery are tested and named responders are available.
11. No Severity 1 or Severity 2 defect remains open.
12. Every real data gate in `production.md` is approved before any patient information is entered.

The release owner records the exact Git commit, container digest, database migration state, test evidence, approved exceptions, signatories, and acceptance time. Any later code, configuration, dependency, migration, or infrastructure change creates a new release candidate and requires proportionate retesting.

## 30. Current platform verification

The following checks last ran on 26 August 2026 with Docker Engine 29.7.2 and Docker Compose 5.3.1. They describe the current working candidate. Continuous integration must repeat them against the final commit before they become release evidence.

1. Local, test, staging, and production Compose configuration rendered successfully. The development, test, and production Caddy policies passed `caddy validate` with their intended host settings.
2. The PostgreSQL image built from the official pgBackRest 2.59.0 distribution archive. The archive matched SHA256 `faaf8faa14a6392279654ee216a493fcd07b0c513af4b55fe34faec062cb8875`, and the built image returned `pgBackRest 2.59.0`.
3. The assembled test topology returned HTTP 200 for liveness, readiness, and the application shell through one same origin Caddy endpoint. The database and API published no host ports. The web service could not resolve the private database service, the database could not resolve the web service, and the API alone joined both required networks.
4. The API and notification worker ran as uid 10001. Caddy ran as uid 10002. Each used a read only root filesystem, had no effective Linux capabilities, and could write only to its approved temporary or persistent paths. The runtime database role had no database or schema creation permission.
5. The backend suite passed 113 tests against PostgreSQL 18.6 on Python 3.14.7 with 87 percent measured coverage. It includes direct authorization, state transition, idempotency, append only history, booked schedule integrity, last capacity, first MRN, and simultaneous queue call tests.
6. The frontend suite passed 55 tests with 86.87 percent statement coverage and 88.88 percent line coverage. Formatting, linting, and the Vite production build passed. The built JavaScript was 432.13 kB and 121.12 kB compressed.
7. Six serial Chromium workflows passed against the assembled same origin stack. They covered public navigation and privacy, patient availability, receptionist MFA and check in, patient queue privacy and location guidance, doctor MFA with the assigned operational queue, administrator MFA, and every sidebar destination for all four roles. The sweep reported no page exception, browser console error, or response with status 500 or above.
8. The quick read gate ramped to 50 virtual users, held at 50 for 60 seconds, completed 3,638 requests with no failed check, and measured read p95 at 4.23 milliseconds on the local Docker host. This is only the narrow gate defined in section 22.1. It does not prove write latency, queue freshness, or production capacity.
9. The isolated recovery exercise created an encrypted full backup, verified the repository, cleared only its named synthetic database volume, restored into that clean volume, and recovered the expected marker. It also proved uid 70, zero effective capabilities, a read only root filesystem, and separated database roles. This proves the local container and encryption mechanics. It does not prove the one hour recovery point objective or four hour recovery time objective on approved off host storage.
10. Caddy, shell scripts, and GitHub Actions configuration passed their validators. Strict Trivy scans found zero high or critical findings in the API, web, and PostgreSQL images. The current tracked repository scan found zero high or critical dependency vulnerabilities, Dockerfile misconfigurations, or secrets. Current local `pip-audit` and `npm audit` checks found no known dependency vulnerability. The latest required GitHub security workflow for the application revision also passed Bandit, Semgrep, dependency, configuration, and secret checks.
11. One time sensitive test defect was reproduced shortly after midnight in Asia/Dhaka. The application correctly rejected a check in from the previous service date, but the regression fixture had unintentionally crossed that boundary. The test now uses a stable time on the appointment service date. Its targeted rerun and the complete 113 test suite passed.

The remaining platform release gates require the final committed images and external staging infrastructure. They include the 30 minute authenticated mixed read and write workload, synthetic business integrity reconciliation after that workload, external TLS and certificate monitoring, production SMTP failure handling, restoration from separate approved storage, alert delivery, a schema compatible rollback rehearsal with recorded image digests, and hospital acceptance. None of these items is represented as passed by the local evidence above.
