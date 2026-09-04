# MediQueue Production Pilot Tasks

## 1. Purpose

This file is the working backlog for the hospital operations pilot. The requested three day build window was 15 August 2026 through 17 August 2026. Execution resumed on 22 August 2026 after the interrupted session, so the verification record uses the actual completion date. The pilot is designed for one small hospital, up to 30 doctors, 500 appointments each day, and 50 concurrent users.

The name MediQueue is a temporary development name. The approved hospital name, logo, contact details, privacy notice, and consent text must replace it before real patients use the system.

## 2. Delivery rules

1. Planning documents are completed and reviewed before application scaffolding begins.
2. Synthetic patient and staff data are used in development, tests, demonstrations, and staging.
3. A task is complete only when its acceptance condition is met and its evidence is recorded in the relevant pull request or test report.
4. Critical security, authorization, privacy, data loss, double booking, and queue ordering defects block release.
5. A failed dependency is raised to the delivery lead on the same day. Work may continue only where it does not hide or bypass the dependency.
6. Every database change includes a forward migration, a compatibility review, and a rollback or restore decision.
7. Every external write endpoint supports an `Idempotency-Key`. Every protected endpoint starts with default denial and adds only the permissions it needs.
8. Appointments, payments, consent, queue events, staff access, and administrative changes remain traceable. Records are corrected or deactivated instead of being silently deleted.
9. Accessibility, privacy, security, backup restoration, and concurrency are release work, not later improvements.

## 3. Priorities and ownership

### 3.1 Priority definitions

1. Priority 0 means the production candidate cannot be accepted without the task.
2. Priority 1 means the pilot should include the task unless a Priority 0 issue uses the remaining time.
3. Priority 2 means the work is useful but may be deferred without making the defined pilot unsafe or incomplete.

### 3.2 Delivery roles

1. Delivery lead owns scope, daily acceptance, risk decisions, repository controls, and the final release decision.
2. Backend owner owns the Django API, PostgreSQL schema, authorization, transactions, audit events, notification worker, and backend tests.
3. Frontend owner owns the React application, accessible components, browser state, queue polling, responsive behavior, and frontend tests.
4. Operations owner owns Docker, Caddy, CI, staging, monitoring, backup, restore, deployment, and rollback evidence.
5. Hospital administrator owns configuration decisions, staff lists, hospital wording, retention approval, and administrator acceptance.
6. Receptionist representative owns registration, duplicate review, booking, check in, walk in, queue operation, and payment acceptance.
7. Doctor representative owns schedule, daily queue, patient identity minimums, service start, completion, defer, and no show acceptance.
8. Security and privacy reviewer owns the threat review, access review, go live privacy check, and unresolved risk record.

If one person performs more than one role, the acceptance evidence must still identify which responsibility was exercised.

### 3.3 Current three day execution

The following schedule supersedes the original six day calendar without removing any Priority 0 feature or release gate.

1. Day 1, 15 August 2026, closes implementation and security blockers. It completes all identity, directory, scheduling, appointment, reception, queue, payment, notification, audit, interface, dependency, migration, and permission work. The day ends only when backend and frontend suites are clean on PostgreSQL.
2. Day 2, 16 August 2026, proves the assembled system. It covers same origin container smoke tests, concurrency, 50 user load, accessibility review, dependency and source scans, non root runtime checks, database role separation, encrypted backup, clean restore, migration rehearsal, and rollback rehearsal.
3. Day 3, 17 August 2026, completes review and delivery. It covers the private pull request, required CI checks, synthetic data role walkthroughs, doctor and receptionist UAT evidence where representatives are available, documentation reconciliation, production candidate tagging, and the explicit real data decision.

Work continues in parallel where tasks do not mutate the same files or test data. A failed Priority 0 check immediately becomes the next task. Priority 2 work may be deferred only after all Priority 0 and Priority 1 acceptance conditions pass.

### 3.4 Current execution record

On 4 September 2026, the complete local candidate passed 129 Django tests on PostgreSQL 18.6 with 87 percent coverage, 57 frontend tests with 88.88 percent line coverage, six Chromium role workflows, every role navigation destination, same origin health checks, and the 50 user quick read gate. The load gate completed 3,638 requests with no failed check and a 4.23 millisecond read p95. The encrypted backup and clean isolated restore also passed. Repository CI must repeat the final working tree after the report and provider compatibility changes. External staging, hospital UAT, production SMTP, approved infrastructure, and the real data approvals remain separate gates and must not be described as complete until their named owners provide evidence.

## 4. Foundation work package

### 4.1 Complete the planning record

Priority: 0  
Owner: Delivery lead  
Dependencies: Supplied university PDFs, interface references, and approved scope  
Work: Complete `tasks.md`, `production.md`, `implementation_plan.md`, `audit.md`, `workflow.md`, `bugs.md`, `test.md`, and `advanced_mechanism.md`. Reconcile terms, roles, states, dates, exclusions, and release gates across all eight files.  
Acceptance: All eight files are present, contain no unresolved internal contradiction, and are approved as the baseline before application code is added.

### 4.2 Protect supplied and sensitive material

Priority: 0  
Owner: Delivery lead  
Dependencies: Task 4.1  
Work: Add exact ignore rules for the three supplied PDFs and four supplied images. Ignore local environment files, secrets, production exports, database dumps, uploaded media, generated reports, and local certificates.  
Acceptance: Repository status proves that none of the supplied files or protected categories can enter the first commit accidentally.

### 4.3 Establish the private repository

Priority: 0  
Owner: Delivery lead  
Dependencies: Tasks 4.1 and 4.2  
Work: Initialize `main`, create the private `S-Salehin/mediqueue-hms` repository, and push a documentation only first commit. Configure short lived branches, pull request review, required CI checks, protected deployment environments, secret scanning, and private container packages.  
Acceptance: The remote repository is private, the first commit contains planning and repository safety files only, and branch protection prevents an unchecked production change.

### 4.4 Scaffold the application boundary

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Task 4.3  
Work: Create the Django 5.2 LTS API and React 19 application with JavaScript, Vite, Tailwind CSS, and a shared accessible component foundation. Use Python 3.14 and PostgreSQL 18 in every environment. Add exact dependency lockfiles.  
Acceptance: A new developer can start the approved local services from the documented commands, load the public application shell, and receive successful responses from `/api/v1/health/live/` and `/api/v1/health/ready/`.

### 4.5 Build the local and CI service baseline

Priority: 0  
Owner: Operations owner  
Dependencies: Task 4.4  
Work: Define PostgreSQL, Django, notification worker, frontend build, and Caddy services. Add lint, format check, unit test, migration check, dependency scan, and production build jobs without exposing PostgreSQL outside its private network in deployment.  
Acceptance: A clean CI run installs exact dependencies, checks migrations, runs the initial tests, and produces the application and private container artifacts.

### 4.6 Establish identity and security foundations

Priority: 0  
Owner: Backend owner  
Dependencies: Task 4.4  
Work: Create the custom user model, role assignments, secure session authentication, CSRF controls, staff invitation model, MFA device foundation, login audit, request identifiers, stable API errors, and default deny permission classes.  
Acceptance: Patient and staff sessions can be distinguished, anonymous access is limited to approved public routes, CSRF is enforced on session writes, and role tests prove denial before later features are added.

### 4.7 Establish the design system

Priority: 1  
Owner: Frontend owner  
Dependencies: Task 4.4  
Work: Define typography, color tokens, focus states, form controls, status labels, feedback messages, loading states, responsive navigation, and page shells for public, patient, doctor, reception, and administration areas.  
Acceptance: The component examples meet keyboard navigation and visible focus requirements, work at 320 CSS pixels, and do not depend on color alone to explain status.

### 4.8 Foundation review

Priority: 0  
Owner: Delivery lead  
Dependencies: Tasks 4.1 through 4.7  
Work: Review the planning baseline, repository privacy, authentication boundary, CI result, and open risks with the team.  
Acceptance: The daily record names completed tasks, failed tasks, owners for corrective work, and any approved Priority 2 deferral. No feature work is accepted if the planning first rule was broken.

## 5. Directory and identity work package

### 5.1 Implement hospital structure

Priority: 0  
Owner: Backend owner  
Dependencies: Tasks 4.4 and 4.6  
Work: Implement hospital configuration, departments, locations, chambers, doctor profiles, activation status, and UUID external identifiers. Keep the data model limited to one hospital while retaining explicit hospital identifiers for future interoperability.  
Acceptance: Administrators can create, edit, list, and deactivate each structure through authorized APIs, and public APIs reveal only approved directory fields.

### 5.2 Complete role assignment and staff invitations

Priority: 0  
Owner: Backend owner  
Dependencies: Task 4.6  
Work: Implement administrator controlled invitations for doctor, receptionist, and administrator accounts. Require email verification, password setup, and TOTP MFA enrollment before staff access is active.  
Acceptance: An uninvited user cannot become staff, an invited user cannot use a staff function before MFA enrollment, and every invitation and role change creates an audit event.

### 5.3 Implement patient registration and account claiming

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Task 4.6  
Work: Implement patient self registration with email verification, generated medical record numbers, privacy notice acceptance, and consent recording. Allow receptionists to create an unclaimed profile when a patient has no email. Implement controlled account claiming without merging records automatically.  
Acceptance: Medical record numbers are unique, privacy acceptance is versioned, unclaimed profiles cannot sign in, and a claim requires verified matching evidence plus receptionist or administrator review.

### 5.4 Implement duplicate patient warnings

Priority: 0  
Owner: Backend owner  
Dependencies: Task 5.3  
Work: Search normalized phone, email, name, and date of birth combinations for likely duplicates. Return warnings only to authorized reception and administration users. Never merge profiles automatically.  
Acceptance: Known duplicate fixtures produce a warning, unrelated fixtures do not block registration, and patient users cannot use the search as a directory of other patients.

### 5.5 Implement schedules, closures, and availability

Priority: 0  
Owner: Backend owner  
Dependencies: Task 5.1  
Work: Implement recurring doctor schedules, location and chamber assignment, slot duration, capacity, effective dates, and date specific closures or overrides. Calculate availability in UTC and display it in Asia/Dhaka time.  
Acceptance: Overlapping doctor and chamber rules are rejected, closures remove affected availability, capacity is calculated consistently, and date boundary tests cover Asia/Dhaka conversion.

### 5.6 Build the public directory and staff configuration screens

Priority: 1  
Owner: Frontend owner  
Dependencies: Tasks 5.1 and 5.5  
Work: Build the department and doctor directory, availability view, administrator structure forms, schedule editor, closure editor, and clear empty and error states.  
Acceptance: Public users can find an active doctor and available date without seeing private staff data, while administrators can complete the configuration using keyboard only.

### 5.7 Seed synthetic pilot data

Priority: 1  
Owner: Backend owner  
Dependencies: Tasks 5.1 through 5.5  
Work: Create repeatable synthetic data for departments, locations, doctors, schedules, patients, and consent. Do not copy names, contact details, or signatures from supplied documents.  
Acceptance: The seed is deterministic enough for demonstrations and tests, contains no real personal data, and can be rerun without creating uncontrolled duplicates.

### 5.8 Directory and identity hospital review

Priority: 0  
Owner: Hospital administrator and doctor representative  
Dependencies: Tasks 5.1 through 5.6  
Work: Review department wording, chamber assignment, doctor directory fields, schedule creation, closures, and the staff invitation path.  
Acceptance: Review notes identify accepted behavior and any correction with owner and deadline. A schedule or permission concern that can affect booking remains release blocking.

## 6. Appointment and reception work package

### 6.1 Implement transactional appointment booking

Priority: 0  
Owner: Backend owner  
Dependencies: Task 5.5  
Work: Implement availability reads and appointment creation with PostgreSQL transactions, row locks, unique constraints, capacity checks, request idempotency, and immutable state history.  
Acceptance: Two requests competing for the final place produce one confirmed appointment, repeated requests with the same idempotency key return the original outcome, and no capacity can become negative.

### 6.2 Implement rescheduling and cancellation

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Task 6.1  
Work: Allow authorized patients and receptionists to reschedule a confirmed future appointment or cancel an eligible appointment. Preserve the original booking and every change in history. Do not mutate completed or no show appointments.  
Acceptance: Rescheduling locks old and new capacity in one transaction, cancellation releases capacity once, stale or repeated requests remain safe, and the interface explains every rejected transition.

### 6.3 Build patient appointment journeys

Priority: 0  
Owner: Frontend owner  
Dependencies: Tasks 5.6, 6.1, and 6.2  
Work: Build doctor discovery, date and slot selection, review, confirmation, upcoming appointment, appointment detail, reschedule, and cancellation pages.  
Acceptance: A verified patient can complete each journey on desktop and mobile with keyboard navigation, receives a clear confirmation, and cannot load another patient’s appointment by changing a URL.

### 6.4 Build the receptionist workspace

Priority: 0  
Owner: Frontend owner and backend owner  
Dependencies: Tasks 5.3, 5.4, and 6.1  
Work: Provide patient search, duplicate warning, profile creation, booking, rescheduling, cancellation, today filters, and minimum necessary patient details in a reception focused screen.  
Acceptance: The receptionist representative can complete all named journeys without administrator access, and every sensitive read and write is attributable to the signed in receptionist.

### 6.5 Implement check in and walk in handling

Priority: 0  
Owner: Backend owner  
Dependencies: Tasks 6.1 and 6.4  
Work: Check a confirmed appointment into the correct queue session and allow an authorized receptionist to create and check in a walk in. Allocate the final privacy safe token only during check in.  
Acceptance: Duplicate check in cannot create a second active ticket, a walk in respects the doctor and schedule capacity policy, and the patient’s token contains no patient identity.

### 6.6 Implement onsite payment records

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Tasks 6.1 and 6.4  
Work: Record integer BDT minor units with `unpaid`, `paid_on_site`, `waived`, and `refunded` states. Do not collect or store card details. Require a reason and audit event for waiver, refund, or correction.  
Acceptance: Repeated writes remain idempotent, invalid transitions are rejected, totals can be reconciled from immutable history, and patient responses expose only the patient’s own payment information.

### 6.7 Appointment and reception hospital review

Priority: 0  
Owner: Receptionist representative and hospital administrator  
Dependencies: Tasks 6.1 through 6.6  
Work: Run registration, duplicate warning, booking, rescheduling, cancellation, check in, walk in, and onsite payment scenarios using synthetic data.  
Acceptance: The hospital review signs off each critical flow or records a release blocking defect with severity, evidence, owner, and next test date.

## 7. Queue and notification work package

### 7.1 Implement queue sessions and event history

Priority: 0  
Owner: Backend owner  
Dependencies: Task 6.5  
Work: Implement doctor and schedule queue sessions, transactional token allocation, queue tickets, legal state transitions, and immutable queue event history.  
Acceptance: Tokens are unique within their queue session, history records actor and timestamps, and the database rejects duplicate active tickets and illegal state changes.

### 7.2 Implement doctor and reception queue controls

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Task 7.1  
Work: Implement call next, start service, defer, restore, complete, no show, and operational override actions. Use row locks so only one ticket can become the active called or in service ticket for a queue.  
Acceptance: Simultaneous call next requests cannot activate two patients, required reasons are stored for defer, restore, no show, and override actions, and each action follows the permission matrix.

### 7.3 Implement the Adaptive Arrival Window

Priority: 0  
Owner: Backend owner  
Dependencies: Tasks 7.1 and 7.2  
Work: Implement the calculation in `advanced_mechanism.md`, including the configured duration fallback, latest 20 valid service durations, 70 percent median and 30 percent configured blend after five observations, 5 to 60 minute clamp, median absolute deviation range, confidence label, and recommendation window.  
Acceptance: Fixed datasets reproduce the documented estimates exactly, invalid service records are excluded, the ordering remains first in first out, and no medical priority field changes the result.

### 7.4 Implement privacy safe queue snapshots

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Tasks 7.2 and 7.3  
Work: Return the patient’s token, currently served token, people ahead, estimated wait range, recommended return window, confidence, and last updated time. Support `ETag` and `If-None-Match`. Poll every 10 seconds while active and every 30 seconds while in the background, and mark the display stale after 30 seconds without a successful refresh.  
Acceptance: A patient never receives another patient’s name or identifier, unchanged snapshots return `304 Not Modified`, and offline, stale, reconnecting, and background states are visible and tested.

### 7.5 Implement the notification outbox and worker

Priority: 0  
Owner: Backend owner and operations owner  
Dependencies: Tasks 6.1 and 7.4  
Work: Store in app notifications and transactional email jobs in the same database transaction as the related business event. Process jobs with retry, attempt history, terminal failure handling, and privacy safe templates.  
Acceptance: Booking or queue writes succeed even when email is unavailable, retries do not send an uncontrolled duplicate, failed jobs remain visible to administrators, and emails contain minimal information plus a secure link.

### 7.6 Implement fairness and accuracy records

Priority: 1  
Owner: Backend owner  
Dependencies: Tasks 7.2 and 7.3  
Work: Record queue order inputs, estimate versions, override reasons, prediction ranges, actual service starts, actual durations, notification outcomes, and stale snapshot events without creating a medical triage score.  
Acceptance: An administrator can inspect why an order or estimate was produced, while patients and unauthorized staff cannot access operational analytics about other patients.

### 7.7 Queue and notification hospital review

Priority: 0  
Owner: Doctor representative and receptionist representative  
Dependencies: Tasks 7.1 through 7.5  
Work: Run a complete queue with check in, call, start, defer, restore, complete, no show, concurrent action, email failure, and patient polling scenarios.  
Acceptance: Doctor and reception representatives approve the controls and wording, or every rejected point is entered as a release blocking defect.

## 8. Release hardening work package

### 8.1 Complete role dashboards

Priority: 0  
Owner: Frontend owner and backend owner  
Dependencies: Tasks 5.1 through 7.5
Work: Complete patient, doctor, receptionist, and administrator dashboards with role appropriate summaries, actions, accessible loading behavior, empty states, and failures.  
Acceptance: Each role sees only its approved data and can reach its critical daily task without depending on a hidden or unauthorized route.

### 8.2 Complete administration and audit search

Priority: 0  
Owner: Backend owner and frontend owner  
Dependencies: Tasks 5.1, 5.2, 7.5, and 7.6
Work: Complete hospital configuration, staff state, operational notification failures, audit event filters, and export controls. Prevent audit mutation through application APIs.  
Acceptance: Authorized administrators can investigate an appointment, payment, queue, consent, and staff access event by request identifier or business identifier, and no interface can edit an audit event.

### 8.3 Complete responsive and accessible behavior

Priority: 0  
Owner: Frontend owner  
Dependencies: Tasks 8.1 and 8.2  
Work: Review all critical flows against WCAG 2.2 AA, including semantics, labels, focus order, error association, contrast, reflow, target size, reduced motion, and screen reader announcements for queue changes.  
Acceptance: Automated checks have no serious or critical findings and the keyboard and screen reader manual scenarios in `test.md` pass.

### 8.4 Complete concurrency and load tests

Priority: 0  
Owner: Backend owner and operations owner  
Dependencies: Tasks 6.1, 6.5, 7.1, 7.2, 7.3, and 7.4
Work: Test final slot contention, repeated writes, simultaneous call next, duplicate check in, queue polling, and a 50 concurrent user workload.  
Acceptance: Data invariants hold and measured p95 latency is at most 500 ms for reads and 800 ms for writes, with queue freshness no more than 15 seconds during the approved workload.

### 8.5 Complete security verification

Priority: 0  
Owner: Security and privacy reviewer  
Dependencies: Tasks 8.1 and 8.2  
Work: Review applicable OWASP ASVS 5.0 Level 2 controls, authorization boundaries, object access, session settings, CSRF, MFA, rate limits, lockout, reset, input handling, headers, logging, dependencies, containers, and secret exposure.  
Acceptance: No unresolved critical or high finding remains. Every accepted lower severity risk has an owner, treatment, and review date.

### 8.6 Complete user guidance

Priority: 1  
Owner: Delivery lead and hospital representatives  
Dependencies: Tasks 8.1 through 8.3  
Work: Write short guidance for patients, doctors, receptionists, administrators, incident contacts, queue fallbacks, and known pilot limits.  
Acceptance: A new representative can complete the role’s critical scenario from the guidance without developer assistance.

### 8.7 Release hardening hospital review

Priority: 0  
Owner: Hospital administrator, doctor representative, and receptionist representative  
Dependencies: Tasks 8.1 through 8.6  
Work: Run the complete synthetic data acceptance suite on the release candidate interface.  
Acceptance: Each role signs the recorded UAT result. Any failed critical scenario blocks release work until corrected and rerun.

## 9. Verification and release work package

### 9.1 Run the complete verification suite

Priority: 0  
Owner: Delivery lead  
Dependencies: Tasks 4.8 through 8.6
Work: Run backend, frontend, end to end, permission, state, concurrency, load, accessibility, dependency, container, security, and Django deployment checks from a clean revision.  
Acceptance: All required checks pass, backend domain and API coverage is at least 85 percent, frontend logic coverage is at least 75 percent, and every authorization, transaction, and state path is directly tested regardless of coverage percentage.

### 9.2 Prove backup and clean restoration

Priority: 0  
Owner: Operations owner  
Dependencies: Production environment definition and a staging dataset  
Work: Create an encrypted backup, restore it into a clean isolated environment, verify counts and critical records, and record duration and evidence.  
Acceptance: Restoration succeeds inside the four hour RTO and the available recovery point meets the one hour RPO target. No production secret or personal data appears in the evidence.

### 9.3 Rehearse migration, deployment, and rollback

Priority: 0  
Owner: Operations owner  
Dependencies: Tasks 9.1 and 9.2  
Work: Rehearse image promotion, predeployment checks, database migration, health checks, smoke tests, monitoring, rollback, and restore decision points on staging.  
Acceptance: The procedure is repeatable from the documented commands, rollback is completed or explicitly proven unnecessary for each migration, and service recovery is measured.

### 9.4 Complete browser smoke tests

Priority: 0  
Owner: Frontend owner  
Dependencies: Task 9.3  
Work: Test registration, sign in, booking, reception, queue, payment, and administration on the supported desktop and mobile browser set.  
Acceptance: No critical flow has a browser specific failure, layout obstruction, inaccessible control, or stale asset after deployment.

### 9.5 Complete final hospital UAT

Priority: 0  
Owner: Doctor representative and receptionist representative  
Dependencies: Tasks 9.1 through 9.4  
Work: Repeat the signed critical workflow set on staging with synthetic data and the exact release revision.  
Acceptance: Both representatives sign the revision and every release blocking defect is closed with regression evidence.

### 9.6 Tag and publish the production candidate

Priority: 0  
Owner: Delivery lead  
Dependencies: Tasks 9.1 through 9.5  
Work: Record the change summary, known nonblocking limits, artifact digests, migration set, test evidence, and approval. Tag the production candidate and promote it to staging.  
Acceptance: The tag resolves to the tested immutable artifacts, staging is healthy, and the release record contains no claim that real data use is approved.

### 9.7 Make the real data launch decision

Priority: 0  
Owner: Hospital administrator and security and privacy reviewer  
Dependencies: All gates in section 11  
Work: Review infrastructure, legal and privacy approval, operational ownership, training, staff MFA, security findings, backup, monitoring, incident response, and controlled pilot readiness.  
Acceptance: Real data use begins only after every gate has named evidence and written approval. Otherwise the system remains a synthetic data demonstration and staging pilot.

## 10. Daily UAT responsibilities

1. The delivery lead prepares a short scenario list and the exact revision before each session.
2. The hospital administrator validates names, configuration, permissions, privacy wording, and operational ownership.
3. The receptionist representative performs registration, duplicate review, booking, check in, walk in, queue, payment, and correction tasks without developer intervention.
4. The doctor representative performs schedule review, call, start, defer, restore, complete, and no show tasks without receiving unnecessary patient information.
5. The backend or frontend owner observes failures but does not guide the representative around them. A workaround is recorded as a defect, not treated as acceptance.
6. Each result records date, revision, role, scenario, outcome, evidence, defect identifier when failed, and the person who accepted it.
7. A corrected critical flow is rerun by the hospital role that originally found the problem.

## 11. Real data launch gates

1. A Bangladesh VPS, approved domain, DNS, TLS, and production SMTP service are purchased and configured.
2. The hospital approves its final name, logo, contacts, privacy notice, consent language, retention schedule, access policy, incident process, and operational owner.
3. A qualified reviewer completes the legal mapping for applicable Bangladesh personal data, data management, cyber security, and hospital obligations.
4. Doctor and receptionist representatives sign every critical workflow on the release revision.
5. Production staff accounts are reviewed, TOTP MFA is active, training is complete, and unused access is removed.
6. No unresolved critical or high security finding remains.
7. Backup restoration, deployment rollback, monitoring, alert delivery, incident contacts, one hour RPO, and four hour RTO are tested.
8. A controlled single department pilot succeeds before wider hospital rollout.
9. Synthetic data remain mandatory until all eight preceding gates are approved.

## 12. Deferred work

The following work is outside the current pilot and must not be added by weakening the required scope:

1. Electronic medical record notes, diagnoses, prescriptions, laboratory, pharmacy, inpatient care, beds, and clinical decision support.
2. Insurance, inventory, payroll, accounting, online payment processing, card storage, and financial settlement integrations.
3. SMS, native mobile applications, video consultation, automated medical triage, AI diagnosis, and automatic clinical prioritization.
4. Multi hospital tenancy and cross hospital patient identity resolution.
5. Formal Bangladesh Core FHIR conformance. The pilot keeps stable external identifiers needed for later mapping but does not claim conformance.
6. Advanced forecasting beyond the documented median based Adaptive Arrival Window.

## 13. Release completion definition

The three day completion plan is complete when the tagged production candidate passes all required tests, hospital UAT is signed for the tested revision, staging is healthy, the backup and rollback evidence is current, all release blocking defects are closed, and the release record states clearly whether the real data gates remain pending.

## 14. Role aware help assistant work package

### 14.1 Implement secure assistant API

Priority: 0
Owner: Backend owner
Dependencies: Authentication, role permissions, directory, appointments, schedules, queues, and payments
Work: Add a bounded authenticated assistant endpoint, role derived access, controlled live queries, clinical refusal, identifier filtering, Groq timeout, and local fallback.
Acceptance: Private answers stay local, no answer can change a record, staff MFA is enforced, and automated API tests pass.

### 14.2 Add assistant interface

Priority: 0
Owner: Frontend owner
Dependencies: Task 14.1
Work: Add an accessible assistant panel to all four authenticated workspaces with role specific suggestions, live data labels, sources, safe route links, loading, failure, keyboard, and mobile states.
Acceptance: Component tests and the assembled browser flow pass without a page exception, console error, server error, or blocked navigation.

### 14.3 Prepare report evidence

Priority: 0
Owner: Delivery lead
Dependencies: Tasks 14.1 and 14.2
Work: Seed only synthetic Bangladeshi names, perform representative demo actions, and capture the public, patient, reception, doctor, administration, queue, and assistant screens in `report_assets/screenshots`.
Acceptance: The manifest identifies every image and no screenshot contains a secret, MFA value, session value, API key, or real patient information.

### 14.4 Approve any external language provider

Priority: 0 for real data
Owner: Hospital administrator and privacy reviewer
Dependencies: Vendor terms and legal review
Work: Review Groq processing purpose, fields, location, retention, training use, access, subprocessors, incident terms, and deletion.
Acceptance: The approval is written and linked to the release record. Until then `GROQ_API_KEY` remains empty in every environment that can receive real patient data.
