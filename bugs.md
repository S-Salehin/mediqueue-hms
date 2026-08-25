# Defect Register and Workflow

## 1. Purpose

This file is the working record for defects, verification, and release impact. The baseline on 14 August 2026 contained university documents and interface references but no transferred application source, database, Git history, or tests. The initial register therefore contains inherited specification, diagram, reference data, privacy, and workflow defects. They are not code bugs.

An implementation defect is added only after there is a revision or runnable environment and evidence that actual behaviour differs from an accepted requirement. A failed assumption in a PDF or mockup remains an inherited defect even if later code would have repeated it.

The full evidence and production decisions are in `audit.md`.

## 2. Defect classes

| Class | Meaning | Example |
| --- | --- | --- |
| `SPEC` | Contradiction, omission, unsupported claim, or ambiguous requirement in the supplied reports | Online payment is required in one report and optional manual tracking appears in another. |
| `ERD` | Defect in the old entity relationship diagram or data design | Appointment “manages” a contact message and no schedule or queue exists. |
| `REF` | Privacy, data consistency, accessibility, or workflow defect in a supplied interface reference | A patient screen shows the full name of the person currently being served. |
| `CODE` | Reproducible failure in application code against an accepted requirement | A patient can retrieve another patient’s appointment by changing a UUID. |
| `DATA` | Migration, seed, constraint, identity, or record integrity defect in implemented data | Two queue tickets receive the same token in one queue session. |
| `OPS` | Deployment, configuration, backup, monitoring, availability, or incident defect | A clean restore cannot meet the approved recovery objective. |
| `SEC` | Implemented security or privacy control failure | CSRF is not enforced on a session authenticated write. |
| `A11Y` | Implemented accessibility failure | The queue update is not announced to a screen reader. |

Security and privacy defects can also be incidents. If personal data may have been exposed, a secret may have leaked, integrity may be compromised, or the service may be under active attack, open the incident process in `production.md` immediately. Do not wait for ordinary bug triage.

## 3. Severity

| Severity | Definition | Examples | Release effect |
| --- | --- | --- | --- |
| `S0 Critical` | Confirmed or likely personal data exposure, authorization bypass, active compromise, unrecoverable corruption, patient misidentification, double booking or queue corruption with no safe reconciliation, or complete critical service loss | Cross patient object access, exposed database backup, two active patients in one doctor queue | Stop release and affected use. Begin incident handling where applicable. |
| `S1 High` | A critical workflow, privacy boundary, financial record, authentication control, backup, notification, or accessibility path is materially wrong and has no safe normal workaround | Staff MFA bypass, incorrect onsite payment, patient unable to book, keyboard user blocked | Blocks the production candidate or real data launch according to scope. |
| `S2 Medium` | Behaviour is incorrect or confusing but a documented safe workaround exists and integrity and confidentiality remain intact | Stale status label with a manual refresh workaround | May proceed only with owner, deadline, recorded workaround, and release approval. |
| `S3 Low` | Localised presentation, wording, or maintainability issue with no material workflow, privacy, accessibility, or integrity impact | Noncritical spacing or copy error | Does not block release but still needs an owner and target. |

Severity follows consequence, not effort. A one line authorization error can be Critical. A large refactor can be Low. An accessibility failure is High when it prevents a user from completing a critical flow.

## 4. Required defect record

Every new defect must contain:

1. Stable identifier and concise title.
2. Defect class and severity.
3. Environment, release, revision, browser or client, and role.
4. Preconditions and the smallest reproducible steps.
5. Expected result from an accepted document or test.
6. Actual result, including exact error code or state when available.
7. Evidence that contains no unnecessary personal data or secret.
8. Data classification and whether incident review is required.
9. Affected records, API, page, queue, or deployment component.
10. Owner, reporter, status, target release, and discovery date.
11. Proposed correction and regression test identifier.
12. Verification result, verifier, revision, environment, and date before closure.

Use synthetic identifiers in screenshots and logs. Never paste passwords, MFA seeds, session cookies, reset links, production connection strings, raw backups, or unrelated patient records into a defect.

## 5. Status workflow

| Status | Meaning | Exit condition |
| --- | --- | --- |
| `Reported` | Evidence has been submitted but not yet assessed. | Triage confirms class, severity, owner, and reproducibility. |
| `Triaged` | Impact and owner are confirmed. | Work begins, a design decision resolves an inherited issue, or authorised deferral is recorded. |
| `In progress` | The owner is correcting the issue. | A reviewable revision and regression test are available. |
| `Ready for verification` | The proposed correction passed the owner’s focused checks. | An independent verifier reruns the original reproduction and relevant regression suite. |
| `Resolved by decision` | An inherited specification, diagram, or reference defect has a clear replacement decision. | The accepted documents agree and implementation tests enforce the decision. It can be reopened if code follows the rejected design. |
| `Closed` | The accepted behaviour is proven in the required environment. | No further action. Closure evidence remains linked. |
| `Deferred` | Work is intentionally outside the current release or has a time limited safe exception. | Named approver, reason, compensating control, owner, and due date are recorded. Critical privacy, security, authorization, integrity, or restore gates cannot be deferred for real data. |
| `Rejected` | Evidence shows expected behaviour, a duplicate, or an invalid report. | The rejection includes proof and links the duplicate when relevant. “Cannot reproduce” alone is not enough. |

The person who implements a correction must not be the only verifier for an `S0` or `S1` defect. A hospital role representative verifies workflow corrections. The security and privacy reviewer verifies authorization, authentication, privacy, secret, and audit corrections.

## 6. Initial inherited defect register

### 6.1 Specification and evidence defects

| ID | Severity | Finding and source | Accepted correction | Status |
| --- | --- | --- | --- | --- |
| SPEC-001 | S0 Critical | Title report p. 5 limits the project to educational and small scale use, while the delivery brief requires a live hospital deployment. No production acceptance exists. | Treat the result as a production candidate. Use synthetic data until every real data gate in `production.md` is signed. | Resolved by decision |
| SPEC-002 | S1 High | React or plain HTML, Tailwind or Bootstrap, and MySQL or SQLite change between Title pp. 2 to 5, Proposal pp. 2 to 4, and Defense pp. 2 and 9. | React 19, Vite, Tailwind CSS, Django 5.2 LTS, and PostgreSQL 18 in every environment. | Resolved by decision |
| SPEC-003 | S0 Critical | The documents promise patient records, Title p. 5 excludes EMR, and the booking image requests symptoms. Data purpose and retention are undefined. | Administrative patient records only. Remove symptom and clinical note collection from v1. | Resolved by decision |
| SPEC-004 | S1 High | Title pp. 3 to 5 define admin, doctor, and patient, while reception work required by a hospital has no role or permission definition. | Add a receptionist role with explicit registration, booking, check in, walk in, queue, and onsite payment permissions. | Resolved by decision |
| SPEC-005 | S1 High | Title pp. 4 to 5 require online payment, but Defense p. 8 leaves a gateway or manual tracking undecided. | Record onsite BDT payments only. Do not store card data or integrate a gateway in v1. | Resolved by decision |
| SPEC-006 | S1 High | “Real time” dashboard and queue claims have no freshness target, transport, offline state, or privacy definition. | Use conditional polling, a 15 second connected freshness target, and visible stale and reconnecting states. | Resolved by decision |
| SPEC-007 | S1 High | All five academic references on Title p. 5 are contradicted or unverifiable as written. | Remove them and use the verified sources listed in `audit.md`. Recheck every final citation before university submission. | Triaged |
| SPEC-008 | S1 High | Defense p. 7 claims working pages, authentication, schema, and routing, but no code, history, schema, or tests were transferred. Defense p. 9 says GitHub “if used.” | Start from scratch and never report inherited implementation as present. Link future progress claims to a revision and test evidence. | Resolved by decision |
| SPEC-009 | S1 High | Defense p. 10 treats hosting as optional and estimates zero to 1,000 BDT, omitting production operations and protection. | Use the cost and topology assumptions in `production.md`. Hospital purchase and approval remain go live blockers. | Resolved by decision |
| SPEC-010 | S1 High | Defense p. 6 gives no reproducible needs assessment, respondent roles, instruments, findings, or hospital approval. | Complete recorded doctor, receptionist, administrator, and privacy review and UAT before real data. | Triaged |
| SPEC-011 | S1 High | Proposal p. 4 claims suitability for hospitals of all sizes while Title p. 5 says small scale and no load evidence exists. | Limit claims to one hospital, 30 doctors, 500 daily appointments, and 50 concurrent users after tests pass. | Resolved by decision |
| SPEC-012 | S2 Medium | Title p. 4 presents common framework choices as novelty without evaluation or prior art boundaries. | Describe only the adaptive arrival range and fairness audit combination as the contribution. Do not claim a worldwide first. | Resolved by decision |

### 6.2 Old ER diagram defects

| ID | Severity | Finding on Defense p. 5 | Accepted correction | Status |
| --- | --- | --- | --- | --- |
| ERD-001 | S0 Critical | `ADMIN.password` is a general string and patient or doctor identities, roles, MFA, sessions, invitations, and login audit do not exist. | Use Django identity, hashed passwords, role assignments, invitations, MFA, secure sessions, and login audit. | Resolved by decision |
| ERD-002 | S0 Critical | The diagram defines an FK legend but does not mark apparent foreign keys. It also gives `APPOINTMENT` an invalid “manages” relationship to `CONTACT_MESSAGE` and draws unnamed links among admin, contact, and about data. | Replace the diagram with explicit migration backed foreign keys and only real business relationships. | Resolved by decision |
| ERD-003 | S0 Critical | No schedule, closure, capacity, queue, check in, state history, idempotency, or uniqueness model can prevent double booking or queue corruption. | Add schedules, exceptions, transactional appointments, queue sessions, tickets, event histories, row locking, and database constraints. | Resolved by decision |
| ERD-004 | S1 High | Appointment status, gender, phones, email, reason, and timestamps have no constraints, format, timezone, or deletion policy. | Use constrained choices, E.164 phone values, normalized email, UTC timestamps, Asia/Dhaka display, deactivation, and correction history. | Resolved by decision |
| ERD-005 | S1 High | MRN, account claiming, duplicate review, consent, payment, notifications, audit, and UUID external identifiers are absent. | Add the production data types named in the implementation plan and verify their permission and retention rules. | Resolved by decision |

### 6.3 Interface and reference data defects

| ID | Severity | Finding and source | Accepted correction | Status |
| --- | --- | --- | --- | --- |
| REF-001 | S0 Critical | The patient dashboard image `(2)` shows the full name of the patient currently being served. | Patient queue responses contain tokens and the signed in patient’s own data only. Add serializer and browser privacy regression tests. | Resolved by decision |
| REF-002 | S1 High | Serial 12 identifies Arif on booking image `(1)` and Hasan on doctor image `(3)`. Serial 15 identifies Arif on patient image `(2)` and Nusrat on doctor image `(3)` for the apparent same doctor and date. | Generate all fixtures from one relational seed. Enforce token uniqueness within a queue session. | Resolved by decision |
| REF-003 | S1 High | Booking image `(1)` issues a final serial before arrival or check in. | Allocate the final privacy safe token only when reception checks the patient in. | Resolved by decision |
| REF-004 | S1 High | Booking and patient images show one approximate wait value without confidence, range, last update, stale state, or failure explanation. | Show a wait range, confidence label, last updated time, and stale or reconnecting status. | Resolved by decision |
| REF-005 | S1 High | Doctor image `(3)` offers ambiguous one click “Skip / Next” and completion actions without reason, legal transition, concurrency protection, or audit. | Use explicit call, start, defer, restore, complete, no show, and override actions with required reasons where defined and immutable history. | Resolved by decision |
| REF-006 | S1 High | Login image defaults “Remember me” to selected, shows no staff MFA or invitation state, and makes an unsupported “data is safe” claim. | Persistent sign in is off by default. Staff MFA and invitation controls are mandatory. Remove blanket assurances. | Resolved by decision |
| REF-007 | S2 Medium | Booking image uses ratings, reviews, a verified badge, experience, institution, fee, instant confirmation, and a support number without a stated owner or source. | Display only hospital approved doctor and fee data. Remove ratings and verification unless a governed source and workflow are later approved. | Resolved by decision |
| REF-008 | S1 High | Static images do not specify keyboard use, focus, error association, status announcements, contrast, reflow, or screen reader output. | WCAG 2.2 AA acceptance applies to complete workflows, not visual similarity. | Triaged |

## 7. Implementation defect register

No implementation defect existed at the audit baseline because no runnable application or source revision was supplied. The following defects were found during implementation and closed before repository review. Do not close an inherited defect merely because a file or screen has been created. Close the related implementation risk only when its acceptance and regression tests pass.

| ID | Severity | Environment and revision | Expected and actual result | Owner | Status | Regression test |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-001 Superseded account link could remain queued | S1 High | Local test stack, working candidate | A worker must send only an active single use link. Earlier verification, reset, claim, or invitation jobs could otherwise outlive their token. | Backend owner | Closed 22 August 2026 | Outbox inactive secure link and verification resend tests |
| SEC-002 MFA replacement challenge had no short expiry | S1 High | Local API tests, working candidate | A staff MFA replacement must end after a short bounded session. The intermediate challenge previously depended only on the wider session controls. | Backend owner | Closed 22 August 2026 | MFA replacement expiry and one time authenticator tests |
| CODE-001 Refund correction lacked a reference requirement | S1 High | Local API and service tests, working candidate | Every refund or payment correction must carry a bounded receipt or correction reference. The service previously permitted an empty reference. | Backend owner | Closed 22 August 2026 | Payment legal transition and least privilege API tests |
| CODE-002 Schedule edits could diverge from booked visits | S1 High | Pull request review on commit `11cbe29` | A booked visit must retain the doctor, chamber, location, date, and duration that were confirmed. Structural schedule edits previously changed the referenced template without reconciling its appointments. | Backend owner | Closed 22 August 2026 | Schedule identity and confirmed capacity API regression test |
| OPS-001 Web runtime image exited without serving | S1 High | Disposable Compose test stack, working candidate | The runtime image must start Caddy. The final image inherited no command and exited with status zero. | Operations owner | Closed 22 August 2026 | Same origin Compose health and five Chromium workflows |
| OPS-002 Container coverage file used application directory | S2 Medium | Disposable backend test container, working candidate | Coverage evidence must write to a bounded temporary path. The first run passed all tests but could not save `/app/.coverage`. | Operations owner | Closed 22 August 2026 | Read only backend test container completed 112 tests and the 85 percent gate |
| OPS-003 CI used a removed coverage XML option | S2 Medium | GitHub Actions run 32522373133, commit `7dca466` | A green 112 test run must publish its XML evidence. Coverage 7.15 rejected the older `--output` spelling after the tests and threshold had passed. | Operations owner | Closed 22 August 2026 | Backend workflow uses the supported `coverage xml -o` command |
| TEST-001 Late check in regression depended on the wall clock | S2 Medium | Local PostgreSQL test stack, 26 August 2026 | The late arrival test must pass at every hospital local time. It subtracted 16 minutes from the real clock and crossed into the previous service date shortly after midnight. The fixture now uses a stable time on the appointment service date. | Backend owner | Closed 26 August 2026 | Targeted late check in test and complete 113 test backend suite |

## 8. Triage and correction process

1. Confirm whether the report is an inherited defect, implementation defect, or incident.
2. Protect evidence. Redact personal data and secrets before attaching it.
3. Reproduce in the lowest safe environment. Never experiment on real patient records to prove a bug.
4. Assign severity from consequence and identify every affected role and state.
5. Stop release work for an `S0`. Escalate a suspected exposure or compromise through `production.md`.
6. Correct the underlying invariant, permission, state transition, or data flow. Do not hide a backend defect with interface wording.
7. Add a regression test at the lowest useful layer and an end to end test when the user journey or authorization boundary changed.
8. Review migrations, audit effects, existing records, notification side effects, and rollback needs.
9. Deploy to staging and let the appropriate hospital or security representative rerun the original scenario.
10. Record verification evidence and close only after the related suite passes.

## 9. Release rules

1. Any open `S0` blocks all release and real data use.
2. Any open `S1` in authentication, authorization, privacy, booking integrity, patient identity, queue ordering, payment integrity, audit, backup restore, deployment rollback, or a critical accessible workflow blocks real data launch.
3. An `S2` exception needs a named owner, safe workaround, compensating control, approver, and deadline. It is reviewed at every release decision.
4. An `S3` may ship when it has no hidden accessibility, privacy, or workflow impact and remains assigned.
5. A correction that changes a public API, state machine, database constraint, permission, retention rule, or operator workflow requires the matching documentation and tests in the same revision.
6. Reopened defects retain their original identifier and history.
7. A production incident is not closed by closing its triggering bug. Incident recovery, notification decision, reconciliation, and review remain separate records.

## 10. Minimum regression expectations

| Defect area | Required regression evidence |
| --- | --- |
| Authorization or privacy | Cross user and cross role denial at API level, response field inspection, and browser verification |
| Booking integrity | Last slot contention, repeated idempotency key, capacity boundary, cancellation, and reschedule tests |
| Queue integrity | Simultaneous call next, duplicate check in, legal transitions, token uniqueness, one active service, and event history tests |
| Patient identity | Duplicate warning, unclaimed profile, claim approval, no automatic merge, and correction audit tests |
| Payment | Repeated write, invalid transition, integer amount, reconciliation, role boundary, and immutable history tests |
| Notification | Mail outage, retry, duplicate prevention, terminal failure, minimal content, and business transaction independence tests |
| Authentication | Invitation, verification, MFA enrolment, lockout, reset, session expiry, CSRF, and logout tests |
| Accessibility | Keyboard completion, focus order, error announcement, queue status announcement, contrast, zoom, and mobile reflow tests |
| Operations | Empty database migration, staging smoke, rollback, alert delivery, encrypted backup, and clean restore tests |

The register is reviewed at the end of every build day and before every staging or production candidate release.
