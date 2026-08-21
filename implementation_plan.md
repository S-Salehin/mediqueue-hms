# MediQueue Implementation Plan

## 1. Product goal

The first release is a production candidate for one small hospital. It supports patient appointment access and the daily work of doctors, receptionists, and hospital administrators. The expected pilot load is up to 30 doctors, 500 appointments each day, and 50 concurrent users.

The system manages hospital structure, doctor schedules, patient registration, appointments, check in, walk ins, live queues, estimated wait ranges, onsite payment records, in app notifications, email notifications, consent, and business audit events.

This is not an electronic medical record. It does not store clinical notes, symptoms, diagnoses, prescriptions, laboratory results, or treatment decisions. Queue order remains operational first in first out order and never becomes automated medical triage.

## 2. Implementation principles

1. Use one versioned API and one documented meaning for every state.
2. Deny protected access unless a role and object rule explicitly allow it.
3. Keep private patient data out of public directory, queue, log, email subject, URL, and analytics fields.
4. Protect competing writes with PostgreSQL transactions, row locks, idempotency records, and database constraints.
5. Record business history separately from current state so a correction never erases what happened.
6. Store timestamps in UTC and display them in `Asia/Dhaka`.
7. Store money as integer BDT minor units. Do not accept or store card details.
8. Use synthetic data until every real data gate in `production.md` is approved.
9. Prefer a small reliable operational design over infrastructure that the hospital cannot maintain.
10. Keep the development name configurable because MediQueue is not approved production branding.

## 3. Technology baseline

1. The browser application uses React 19 with JavaScript, Vite, Tailwind CSS, React Router, and an accessible custom component system.
2. The API uses Python 3.14, Django 5.2 LTS, and Django REST Framework.
3. PostgreSQL 18 is the only application database in local, CI, staging, and production environments. SQLite and MySQL are not supported.
4. Caddy terminates TLS, serves the built browser assets, and proxies `/api/v1/` to Django on the same origin.
5. Gunicorn runs the Django web process. A separate Django management process handles the database notification outbox.
6. Authentication uses secure Django sessions and CSRF protection. Authentication tokens are never stored in browser local storage or session storage.
7. Queue updates use conditional HTTP polling. Redis and WebSockets are not part of the pilot.
8. Direct and transitive dependencies are exact pinned in committed lockfiles. Container images are referenced by immutable release tags or digests in production.

## 4. Runtime architecture

### 4.1 Request path

1. A browser connects to Caddy over HTTPS.
2. Caddy serves the React application for browser routes and sends `/api/v1/` requests to Django.
3. Django validates the session, CSRF token, role, object access, request body, and idempotency key before calling a domain service.
4. The domain service opens a PostgreSQL transaction for any competing or multi record write.
5. The business record, history, audit event, and any notification outbox entry are committed together.
6. The API returns the stable response or error contract with a request identifier.
7. The outbox worker claims pending jobs from PostgreSQL, sends approved email through SMTP, and records the delivery result.

### 4.2 Production services

1. `caddy` is the only public web service.
2. `web` runs the Django API through Gunicorn.
3. `worker` runs the notification outbox processor from the same application image as `web`.
4. `postgres` runs on a private container network and has no public port.
5. The approved SMTP provider is external. An SMTP failure never rolls back an already committed appointment or queue action.
6. Monitoring reads health endpoints, structured logs, host metrics, database status, backup status, and outbox failure counts.

### 4.3 Logical backend modules

1. `accounts` owns users, sessions, role assignments, staff invitations, email verification, MFA, password reset, and login audit.
2. `directory` owns hospital configuration, departments, locations, chambers, doctor profiles, and public directory projections.
3. `patients` owns patient profiles, medical record numbers, duplicate warnings, account claims, privacy notice versions, and consent.
4. `scheduling` owns recurring schedules, exceptions, slot calculation, capacity, and closures.
5. `appointments` owns booking, rescheduling, cancellation, appointment history, check in coordination, and walk ins.
6. `queueing` owns queue sessions, tickets, actions, estimates, snapshots, fairness records, and queue event history.
7. `payments` owns onsite payment state and immutable payment history.
8. `notifications` owns in app notifications, preferences, outbox jobs, retry, and delivery history.
9. `auditing` owns immutable business audit events, request correlation, authorized search, and controlled export.

Modules communicate through explicit service functions. Views and serializers do not contain booking, capacity, queue order, payment transition, or permission policy.

## 5. Data model

### 5.1 Shared data rules

1. Every externally addressable record has a UUID public identifier. Sequential database identifiers, where used internally, are never exposed as object authority.
2. Mutable records contain `created_at`, `updated_at`, and activation state where deactivation is allowed.
3. Business history records are append only through application code.
4. Contact numbers are normalized to E.164. Email comparison is case insensitive.
5. All calendar input is validated in the hospital timezone and persisted as UTC instants where it represents a moment.
6. Foreign keys use restrictive deletion for business records. Doctors, patients, schedules, and configuration with history are deactivated instead of hard deleted.

### 5.2 Identity and access

1. `User` contains the unique normalized email when one exists, password hash, verification state, active state, staff invitation state, and last authentication timestamps. It contains no role specific medical or employment fields.
2. `RoleAssignment` links one user to one of `patient`, `doctor`, `receptionist`, or `administrator`. A staff role can be granted only through an accepted staff invitation.
3. `StaffInvitation` stores invited email, intended role, single use token digest, expiry, inviter, acceptance time, and revocation time.
4. `StaffMFADevice` stores the owner, encrypted TOTP secret, confirmation state, recovery code digests, last used counter, and revocation time.
5. `LoginAudit` stores user when known, result, time, request identifier, normalized network context, and safe client context. It never stores a password, session identifier, CSRF token, MFA secret, or reset token.

### 5.3 Hospital directory

1. `Hospital` stores configurable display name, short name, logo reference, timezone, currency, contact details, active privacy notice, and operational settings. The pilot permits one active hospital.
2. `Department` belongs to the hospital and stores an approved name, public description, display order, and active state.
3. `Location` belongs to the hospital and stores a name, public address, contact details, and active state.
4. `Chamber` belongs to a location and stores a unique local name or room code and active state.
5. `DoctorProfile` links a doctor user to a public doctor code, approved display name, professional designation, registration reference if approved for display, department assignments, biography, consultation fee in BDT minor units, and active state.

### 5.4 Patients and consent

1. `PatientProfile` stores a unique generated medical record number, optional claiming user, approved identity fields, normalized contact fields, date of birth, sex value where required by the hospital, claimed state, and active state.
2. An unclaimed patient profile may be created only by reception or administration. It cannot authenticate until the account claim workflow is approved.
3. `PrivacyNoticeVersion` stores an immutable version identifier, effective time, approved content, and publication state.
4. `ConsentRecord` stores patient, notice version, consent purpose, decision, collection channel, actor when assisted, time, and request identifier. A later decision adds a new record rather than altering an earlier record.
5. Duplicate detection stores no confidence claim as fact. It produces a warning for authorized review and never merges profiles automatically.

### 5.5 Schedules and availability

1. `Schedule` links one doctor to one location and chamber. It stores weekday, local start time, local end time, slot duration in minutes, capacity per slot, effective date range, and active state.
2. `ScheduleException` targets a schedule and date. It either closes a period or supplies an approved replacement period and capacity. The exception records its reason and actor.
3. Overlapping active schedules for the same doctor or chamber are rejected for the same effective period.
4. Availability is computed from the schedule and exception, then reduced by active confirmed appointment capacity inside a transaction when a booking is made.
5. Slots are returned as UTC start and end timestamps with an Asia/Dhaka display value. Past slots and closed periods are never bookable.

### 5.6 Appointments

1. `Appointment` links hospital, patient, doctor, department, location, chamber, schedule, start time, end time, source, status, booking actor, and current payment state reference.
2. Appointment source is `patient`, `reception`, or `walk_in`.
3. Appointment status is exactly `confirmed`, `cancelled`, `completed`, or `no_show`.
4. `AppointmentHistory` records creation, rescheduling, cancellation, completion, no show, actor, reason where required, previous values, new values, and request identifier.
5. Rescheduling changes the time and allocation of a confirmed appointment but does not introduce a separate appointment status. Old and new capacity are changed within one transaction.
6. Cancelled, completed, and no show appointments are terminal. A correction requires an authorized administrative event and may create a replacement appointment without rewriting history.

### 5.7 Queue

1. `QueueSession` identifies one doctor, location, chamber, service date, and operating state. It stores the next token sequence and the active called or in service ticket reference.
2. `QueueTicket` links one appointment and one queue session. It stores a privacy safe token, allocation sequence, check in time, current queue state, call time, service start, service end, defer metadata, and last transition time.
3. Queue state is exactly `waiting`, `called`, `in_service`, `deferred`, `completed`, `no_show`, or `cancelled`.
4. `QueueEvent` stores every transition and override with actor, time, previous state, new state, reason when required, request identifier, and the ordering facts used.
5. Only one active queue ticket may exist for an appointment. A queue session may have only one ticket in the combined called or in service position at a time.
6. `QueueEstimateRecord` stores the calculation version, sample count, configured duration, observed median, observed median absolute deviation, point estimate, wait bounds, people ahead, recommendation, confidence, and creation time.

### 5.8 Payments

1. `PaymentRecord` links one appointment to an integer amount in BDT minor units, state, collection channel, recorder, time, and optional approved reference.
2. Payment state is exactly `unpaid`, `paid_on_site`, `waived`, or `refunded`.
3. `PaymentHistory` records every state or amount correction with actor, reason, old value, new value, and request identifier.
4. The model has no card number, security code, magnetic stripe data, bank credential, or online payment token field.

### 5.9 Notifications and audit

1. `Notification` stores an in app message for one user, approved category, safe title, safe body, related public identifier, created time, and read time.
2. `NotificationPreference` stores permitted email and in app choices. Mandatory security and operational notices cannot be disabled where policy requires delivery.
3. `NotificationOutbox` stores an approved template key, minimal template data, recipient, state, attempt count, next attempt time, last safe error category, and related business event.
4. `NotificationAttempt` records each claimed send without storing rendered sensitive content in logs.
5. `AuditEvent` stores event type, actor, subject type and UUID, action, safe structured changes, time, request identifier, and reason where required. The application provides no update or delete API for audit events.
6. `IdempotencyRecord` stores the authenticated actor, route scope, key digest, request digest, processing state, response status, safe response body, and expiry. Reuse with a different request digest is rejected.

## 6. Roles and permission rules

### 6.1 Patient

1. A patient can read and update the approved fields of their own claimed profile.
2. A patient can read, book, reschedule, or cancel only their own eligible appointments.
3. A patient can read only their own queue token, estimate, notifications, consent history, and payment summary.
4. A patient cannot search other patients, create a final queue token, operate a queue, record payment, or read staff audit data.

### 6.2 Doctor

1. A doctor can read their own schedule and the minimum identity fields for patients assigned to their appointments and current queue.
2. A doctor can call, start, defer, restore, complete, or mark no show only in their own active queue sessions.
3. A doctor cannot change hospital structure, assign roles, merge patients, alter payment records, or read another doctor’s queue unless separately granted an administrator role and acting through that role.

### 6.3 Receptionist

1. A receptionist can search patients using approved fields, review duplicate warnings, create an unclaimed profile, book and manage appointments, check patients in, create walk ins, and operate authorized queues.
2. A receptionist can record approved onsite payment actions and corrections that policy assigns to reception.
3. A receptionist cannot assign staff roles, change security policy, read MFA material, edit immutable history, or access clinical data because the pilot stores none.

### 6.4 Administrator

1. An administrator can manage staff invitations, role activation, hospital configuration, departments, locations, chambers, doctors, schedules, closures, reporting configuration, and authorized audit search.
2. An administrator can correct operational records only through named actions that require a reason and create history. Direct history mutation is not permitted.
3. An administrator cannot retrieve password hashes, MFA secrets, raw reset tokens, or secrets from the application interface.

### 6.5 Enforcement

1. Every protected view declares an allowed role set and filters its queryset before object lookup.
2. Object permission is checked again before serialization or mutation.
3. Serializer fields use role specific projections so possession of a UUID cannot reveal an unauthorized field.
4. Staff MFA and active invitation state are checked at session establishment and for approved sensitive reauthentication points.
5. Authorization denial is recorded safely without revealing whether another patient object exists.

## 7. API contract

### 7.1 General rules

1. The base path is `/api/v1/`.
2. JSON uses `snake_case`, UUID strings, ISO 8601 UTC timestamps, and integer `amount_minor` values with currency `BDT`.
3. Session cookies are `Secure`, `HttpOnly`, and use the approved `SameSite` policy. Browser writes include the Django CSRF header.
4. Every response includes or exposes an `X-Request-ID`. Client supplied request identifiers are validated before reuse.
5. External `POST`, `PUT`, `PATCH`, and action requests accept `Idempotency-Key`. Required high risk routes reject a missing key.
6. Queue snapshot responses include an `ETag`. A matching `If-None-Match` returns `304 Not Modified` with no patient content.
7. List routes use bounded pagination, explicit ordering, and allowlisted filters.
8. Sensitive fields never appear in URLs, cache keys, logs, or error details.

### 7.2 Error shape

Every API error uses the following fields:

1. `status` contains the HTTP status integer.
2. `code` contains a stable machine readable code.
3. `title` contains a short safe summary.
4. `detail` contains a safe human explanation.
5. `field_errors` maps approved request fields to validation messages and is empty when no field error applies.
6. `request_id` contains the support correlation identifier.

Validation, conflict, permission, authentication, rate limit, and server errors keep this shape. A server error does not expose a traceback, query, secret, internal path, or another user’s data.

### 7.3 Authentication and profile routes

1. `GET /api/v1/auth/csrf/` issues the CSRF cookie and safe token bootstrap response.
2. `GET /api/v1/auth/session/` returns the signed in user’s approved identity, roles, MFA state, and permissions.
3. `POST /api/v1/auth/login/` starts a patient session or the staff MFA challenge.
4. `POST /api/v1/auth/mfa/verify/` completes the staff session.
5. `POST /api/v1/auth/logout/` ends the session.
6. `POST /api/v1/auth/register/` creates a patient registration pending email verification.
7. `POST /api/v1/auth/email/verify/` consumes a single use verification token.
8. `POST /api/v1/auth/email/resend/` returns one generic accepted response and replaces any earlier unused verification link only when an unverified account exists.
9. `POST /api/v1/auth/password/forgot/` creates a privacy safe reset request.
10. `POST /api/v1/auth/password/reset/` consumes a single use reset token and revokes existing sessions according to policy.
11. `GET` and `PATCH /api/v1/me/patient-profile/` read and update the patient’s approved fields.
12. `GET /api/v1/me/consents/` lists the patient’s consent history.
13. `POST /api/v1/me/consents/` records a new versioned decision.

### 7.4 Directory and scheduling routes

1. `GET /api/v1/public/hospital/` returns approved public branding and contact details.
2. `GET /api/v1/public/departments/` lists active departments.
3. `GET /api/v1/public/doctors/` lists active approved doctor fields with allowlisted filters.
4. `GET /api/v1/public/doctors/{doctor_id}/` returns one public doctor profile.
5. `GET /api/v1/public/doctors/{doctor_id}/availability/` returns bookable slots for an allowed date window.
6. Authorized administrator CRUD routes use `/api/v1/admin/departments/`, `/api/v1/admin/locations/`, `/api/v1/admin/chambers/`, `/api/v1/admin/doctors/`, `/api/v1/admin/schedules/`, and `/api/v1/admin/schedule-exceptions/`.
7. Deactivation uses an explicit action. Business records with history are not deleted through public APIs.

### 7.5 Patient and appointment routes

1. `GET /api/v1/reception/patients/` performs authorized patient search with bounded results.
2. `POST /api/v1/reception/patients/duplicate-check/` returns possible matches for human review.
3. `POST /api/v1/reception/patients/` creates an assisted or unclaimed profile.
4. `POST /api/v1/reception/patients/{patient_id}/claim-invitations/` starts the controlled claiming process.
5. `GET` and `POST /api/v1/appointments/` list accessible appointments or book one.
6. `GET /api/v1/appointments/{appointment_id}/` returns one authorized appointment.
7. `POST /api/v1/appointments/{appointment_id}/reschedule/` moves an eligible confirmed appointment transactionally.
8. `POST /api/v1/appointments/{appointment_id}/cancel/` cancels an eligible confirmed appointment once.
9. `POST /api/v1/reception/appointments/{appointment_id}/check-in/` allocates the final queue token.
10. `POST /api/v1/reception/walk-ins/` creates the appointment and check in result through one idempotent service.

### 7.6 Queue, payment, notification, and administration routes

1. `GET /api/v1/queues/{queue_id}/snapshot/` returns a role specific privacy safe snapshot.
2. `POST /api/v1/queues/{queue_id}/call-next/` calls the earliest eligible waiting ticket.
3. `POST /api/v1/queue-tickets/{ticket_id}/start/` begins service.
4. `POST /api/v1/queue-tickets/{ticket_id}/defer/` defers an eligible ticket and requires a reason.
5. `POST /api/v1/queue-tickets/{ticket_id}/restore/` returns a deferred ticket to the documented fair position and requires a reason.
6. `POST /api/v1/queue-tickets/{ticket_id}/complete/` completes service.
7. `POST /api/v1/queue-tickets/{ticket_id}/no-show/` marks an eligible ticket as no show and requires a reason.
8. `POST /api/v1/queue-tickets/{ticket_id}/cancel/` cancels an eligible queued visit through an authorized appointment cancellation.
9. `GET /api/v1/appointments/{appointment_id}/payment/` returns the authorized payment summary.
10. `POST /api/v1/appointments/{appointment_id}/payment/actions/` records `paid_on_site`, `waived`, `refunded`, or an approved correction.
11. `GET /api/v1/notifications/` lists the signed in user’s notifications.
12. `POST /api/v1/notifications/{notification_id}/read/` marks the user’s notification as read.
13. `GET` and `PATCH /api/v1/notification-preferences/` manage the signed in user’s permitted choices.
14. `POST /api/v1/admin/staff-invitations/` creates a staff invitation.
15. `GET /api/v1/admin/audit-events/` performs allowlisted, bounded audit search.
16. `GET /api/v1/dashboards/{role}/` returns one role specific summary and rejects a role not active in the current session.
17. `GET /api/v1/health/live/` reports process liveness without dependencies or sensitive details.
18. `GET /api/v1/health/ready/` reports whether the process can safely accept traffic.

## 8. State transitions

### 8.1 Appointment transitions

1. Creation produces `confirmed` after capacity is reserved.
2. `confirmed` may become `cancelled` after policy and authorization checks.
3. `confirmed` may become `completed` only when its queue ticket completes.
4. `confirmed` may become `no_show` only when the authorized queue action marks no show.
5. Rescheduling keeps the state `confirmed`, changes its allocation, and appends history.
6. `cancelled`, `completed`, and `no_show` are terminal.

### 8.2 Queue transitions

1. Check in creates `waiting`.
2. `waiting` may become `called`, `deferred`, `no_show`, or `cancelled`.
3. `called` may become `in_service`, `deferred`, `no_show`, or `cancelled`.
4. `in_service` may become `completed`.
5. `deferred` may become `waiting`, `no_show`, or `cancelled`.
6. `completed`, `no_show`, and `cancelled` are terminal.
7. Defer, restore, no show, cancellation after check in, and any operational override require a reason and queue event.
8. An approved administrative correction never deletes the original event. It appends an override event and must preserve first in first out fairness unless the recorded operational reason explains the exception.

### 8.3 Payment transitions

1. A new appointment begins with `unpaid`.
2. `unpaid` may become `paid_on_site` or `waived`.
3. `paid_on_site` may become `refunded`.
4. An authorized correction may return `waived` to `unpaid` before completion, with a required reason.
5. `refunded` is terminal. A later collection requires a separate approved record, not rewriting the refunded event.

### 8.4 Notification outbox transitions

1. A committed business event creates `pending`.
2. A worker claim changes `pending` or retry eligible `failed` to `processing` under a row lock.
3. Successful delivery changes `processing` to `sent`.
4. A temporary failure changes `processing` to `failed` with a bounded next attempt time.
5. Exhausted or permanent failure changes the job to `dead` and raises an operational alert.
6. Worker recovery returns an abandoned `processing` job to retry only after the lease expires.

## 9. Browser routes and interface behavior

### 9.1 Public routes

1. `/` explains the approved service and presents directory and sign in actions.
2. `/doctors` supports department and availability discovery.
3. `/doctors/:doctorId` shows approved profile fields and bookable availability.
4. `/sign-in`, `/register`, `/verify-email`, `/forgot-password`, and `/reset-password` handle patient identity journeys.
5. `/privacy` shows the active approved privacy notice and contact path.

### 9.2 Patient routes

1. `/patient` is the patient dashboard.
2. `/patient/appointments` lists the patient’s appointments.
3. `/patient/appointments/new` runs doctor, date, slot, review, and confirmation steps.
4. `/patient/appointments/:appointmentId` shows one authorized appointment, queue entry when checked in, and payment summary.
5. `/patient/queue/:queueId` shows only the patient’s token, current served token, people ahead, wait range, recommended arrival window, confidence, connection state, and last update.
6. `/patient/notifications`, `/patient/profile`, and `/patient/privacy` manage the patient’s own messages, approved profile fields, and consent decisions.

### 9.3 Doctor routes

1. `/doctor` shows today’s assigned schedule and queue summary.
2. `/doctor/schedule` shows the doctor’s authorized schedule in read only form for the pilot.
3. `/doctor/queue/:queueId` provides call, start, defer, restore, complete, and no show controls with minimum patient identity.

### 9.4 Reception routes

1. `/reception` shows today’s operational summary and alerts.
2. `/reception/patients` provides bounded patient search, duplicate review, registration, and claiming assistance.
3. `/reception/appointments` supports booking, rescheduling, cancellation, check in, and walk in handling.
4. `/reception/queues/:queueId` provides authorized queue operation and connection status.
5. `/reception/payments` supports approved onsite payment recording and correction.

### 9.5 Administration routes

1. `/admin` shows hospital operational and configuration status.
2. `/admin/staff`, `/admin/departments`, `/admin/locations`, `/admin/doctors`, and `/admin/schedules` manage approved master data.
3. `/admin/notifications` shows failed outbox jobs without exposing email body content unnecessarily.
4. `/admin/audit` supports bounded investigation by time, actor, event type, request identifier, and subject UUID.
5. `/admin/settings` manages configurable branding and approved operational values, not application secrets.

### 9.6 Shared interface rules

1. Route guards improve navigation but never replace API authorization.
2. A page keeps the prior safe view while a background refresh runs and states when data are stale.
3. Queue pages poll every 10 seconds while visible and every 30 seconds while hidden. They show stale status after 30 seconds without a successful response.
4. Forms retain nonsecret user input after a recoverable validation failure and focus the error summary.
5. Status is communicated through text and semantics, not color alone.
6. Critical workflows support keyboard use, screen readers, 200 percent zoom, and 320 CSS pixel reflow in line with WCAG 2.2 AA.

## 10. Core transactional behavior

### 10.1 Booking

1. Validate actor, patient ownership or reception authority, doctor, slot, and idempotency key.
2. Lock the relevant schedule allocation for the slot.
3. Recalculate effective schedule, exception, current active capacity, and time eligibility inside the transaction.
4. Create one confirmed appointment, appointment history, audit event, payment record, and notification outbox entries.
5. Store the idempotent response and commit once.
6. Return a conflict when capacity is no longer available. Never create an unconfirmed partial booking.

### 10.2 Rescheduling

1. Lock the appointment and both old and new slot allocations in stable order.
2. Verify the appointment is confirmed and the new slot has capacity.
3. Release the old allocation and reserve the new allocation in one transaction.
4. Append appointment history, audit, and notification outbox entries.
5. Return the existing response for an identical repeated idempotency key.

### 10.3 Check in and token allocation

1. Lock the confirmed appointment and target queue session.
2. Reject an existing active queue ticket for the appointment.
3. Increment the queue session token sequence and create the privacy safe ticket in `waiting`.
4. Append queue event, appointment history, audit event, in app notification, and email outbox entry.
5. Return the final token only after commit.

### 10.4 Call next

1. Lock the queue session and reject a second active called or in service ticket.
2. Select the eligible waiting ticket with the earliest effective fair position, using check in order and documented restore behavior.
3. Lock that ticket, change it to `called`, and set it as the session active ticket.
4. Append the queue event, estimate record, audit event, and notifications in the same transaction.
5. A simultaneous caller either receives the idempotent original result or a safe conflict. It cannot call another patient while the first is active.

## 11. Security and privacy controls

1. Apply applicable OWASP ASVS 5.0 Level 2 controls and record evidence in `audit.md` and `test.md`.
2. Require TOTP MFA for doctors, receptionists, and administrators. Encrypt TOTP secrets and store only recovery code digests.
3. Use strong password hashing, throttled login and reset routes, safe account enumeration responses, session rotation, idle and absolute timeouts, and session revocation after sensitive changes.
4. Validate CSRF on session writes. Configure trusted origins explicitly and never use a wildcard production host.
5. Apply allowlisted CORS only if a later approved deployment separates origins. Same origin is the pilot default.
6. Use Django ORM parameterization, strict serializer validation, bounded files and text, safe output encoding, and a restrictive content security policy.
7. Keep secrets outside Git and inject them through the production environment or approved secret storage.
8. Redact health data, tokens, credentials, cookies, email body content, and unnecessary contact data from logs and monitoring.
9. Rate limit authentication, verification, reset, public availability, patient search, booking, queue action, and export routes according to route risk.
10. Audit staff access, role changes, patient search, booking changes, queue actions, payment actions, consent, configuration, and exports.
11. Return the same safe not found response for protected objects that do not exist and those the actor cannot access where disclosure would create an enumeration risk.
12. Do not claim legal compliance or production approval solely because a technical control exists.

## 12. Notifications

1. In app notifications are the primary durable patient message channel.
2. Email templates contain the hospital approved sender, a general event description, time where appropriate, and a secure same origin link.
3. Queue emails do not contain symptoms, specialty, another patient’s identity, or a detailed queue position in the subject line.
4. Booking and queue transactions write an outbox job before commit. The worker sends after commit.
5. Retry uses bounded exponential delays with jitter and a maximum attempt count set in operational configuration.
6. A terminal failure appears on the administrator operational screen and monitoring alert. Staff may retry through an audited action without changing the original business event.
7. Template changes are reviewed as privacy changes and versioned with the release.

## 13. Nonfunctional acceptance

1. At 50 concurrent users, p95 application reads complete within 500 ms and p95 writes within 800 ms under the workload defined in `test.md`.
2. A visible patient queue remains no more than 15 seconds behind a successful server update under the same workload.
3. The monthly availability target for the initial pilot is 99.5 percent.
4. The recovery point objective is one hour and the recovery time objective is four hours.
5. Backend domain and API coverage is at least 85 percent. Frontend logic coverage is at least 75 percent. Every authorization, transaction, and state transition path is tested even if the percentage threshold is already met.
6. Critical patient, doctor, reception, and administration journeys meet WCAG 2.2 AA acceptance scenarios.
7. No unresolved critical or high security finding is permitted in the production candidate.

## 14. Build sequence

1. On 15 August 2026, close every remaining identity, directory, scheduling, booking, reception, queue, payment, notification, audit, interface, dependency, migration, permission, and test blocker. The planning record, repository controls, application scaffold, role interfaces, and main domain flows already exist and are reverified rather than rebuilt.
2. On 16 August 2026, prove the assembled system through PostgreSQL tests, concurrency, same origin container smoke tests, 50 user load, accessibility review, security scans, non root runtime checks, database role separation, encrypted backup, clean restore, migration rehearsal, and rollback rehearsal.
3. On 17 August 2026, run the final suite, complete browser smoke tests and available hospital UAT, reconcile every release document, merge the reviewed private pull request, and tag the production candidate only after every required technical check passes.

## 15. External services and future interoperability

1. The only required pilot integrations are production SMTP, DNS, TLS, monitoring alerts, and encrypted offsite backup storage.
2. Online payments, SMS, insurance, laboratory, pharmacy, identity registry, and third party clinical integrations are excluded.
3. Public UUIDs, medical record numbers, practitioner codes, organization identifiers, location identifiers, appointment identifiers, and UTC timestamps are retained so a future project can map them to the Bangladesh Core FHIR implementation guide.
4. The pilot does not expose a FHIR endpoint and does not claim FHIR conformance.

## 16. Explicit exclusions

1. Electronic medical records, clinical notes, symptoms, diagnoses, prescriptions, laboratory, pharmacy, inpatient care, beds, and treatment plans.
2. Insurance, inventory, payroll, general accounting, card processing, online payments, and financial settlement.
3. SMS, native mobile applications, video consultation, automatic medical triage, AI diagnosis, and clinical decision support.
4. Multi hospital tenancy, cross hospital identity matching, and formal FHIR conformance.
5. Production use of the MediQueue name without hospital and legal approval.

## 17. Completion condition

Implementation is complete when the exact release revision passes the required automated and manual tests, doctor and receptionist representatives sign the critical workflows, staging runs the immutable artifacts, backup and rollback evidence is current, security has no unresolved critical or high finding, and the release record states whether every real data gate has been approved. A working demonstration alone does not authorize real patient data.
