# MediQueue Operational and Delivery Workflow

## 1. Purpose

This file defines how people and records move through the hospital pilot and how the software moves from a change request to a reviewed release. It is the shared operating reference for patients, doctors, receptionists, administrators, developers, and operations staff.

All examples use synthetic data until the real data launch gates are approved.

## 2. Shared workflow rules

1. Every person signs in with their own account. Shared staff accounts are not permitted.
2. Staff access requires an invitation, an active role, and confirmed TOTP MFA.
3. The API checks role and object access on every protected request. A browser route guard is never treated as permission.
4. External write requests carry an `Idempotency-Key`. Repeating the same request returns the first result, while reusing the key for different input is rejected.
5. Appointments, queue events, payments, consent, staff access, and administrative changes create immutable history and an audit event.
6. Reasons are required for defer, restore, no show, queue override, waiver, refund, and approved corrections.
7. Times are stored in UTC and shown in `Asia/Dhaka`. The interface displays the timezone anywhere a date or time could be misunderstood.
8. Patient identity is shown only to an authorized role with a current operational need. Public queue displays and patient queue snapshots use tokens only.
9. A failed email never reverses a successful appointment or queue transaction. It creates a visible retry or terminal delivery failure.
10. Clinical emergency and triage decisions remain outside this system. Staff follow the hospital’s approved emergency procedure and record only the permitted operational outcome.

## 3. Patient self registration

### 3.1 Start registration

1. The patient opens `/register` and reads the current privacy notice.
2. The patient enters the approved identity and contact fields, creates a password, and accepts or declines each versioned consent purpose separately.
3. The browser sends the request with CSRF protection and an idempotency key.
4. The API normalizes email and phone, validates required fields, and checks for likely duplicates without revealing another patient’s details.
5. When a likely existing account can be handled safely, the interface directs the patient to sign in or recover the account. It does not confirm a private account to an unverified person.
6. When registration is accepted, the system creates the inactive user, patient profile, unique medical record number, consent records, audit event, and verification email outbox job in one transaction.

### 3.2 Verify and activate

1. The patient opens the single use verification link before it expires.
2. The API verifies the token digest, intended user, expiry, and unused state.
3. The API marks the email verified, activates patient sign in, consumes the token, and records the event.
4. Reusing an accepted or expired token shows a safe recovery path and does not expose internal token state.
5. The patient signs in and sees only their own profile, appointments, queue token, notifications, consent, and payment summaries.

If the message is lost or the link expires, the patient requests another message from the resend page. The response is identical whether or not an account exists. For an existing unverified account, the transaction invalidates every earlier unused verification token and queued verification message before creating the replacement. A delivered old link cannot become valid again.

### 3.3 Failed or abandoned registration

1. Invalid fields return an accessible error summary and field messages without discarding safe input.
2. Verification delivery failure appears in operations monitoring. The patient can request a replacement through a throttled route.
3. Unverified registrations expire or are reviewed under the approved retention schedule. They are not silently converted into active patients.

## 4. Assisted registration and account claiming

### 4.1 Reception creates an unclaimed patient

1. The receptionist searches normalized phone, email, name, and date of birth fields before creating a record.
2. Possible duplicates are presented as warnings with the minimum fields needed for review. The system never merges records automatically.
3. The receptionist confirms whether to use an existing profile or create a new one and records the approved source of information.
4. If the patient has no usable email, the receptionist creates an unclaimed patient profile with a generated medical record number.
5. An unclaimed profile may hold appointments and queue tickets but cannot sign in.
6. Creation records the receptionist, time, consent collection channel, notice version, and request identifier.

### 4.2 Patient claims an existing profile

1. The receptionist or administrator starts a claim invitation only after locating the correct unclaimed profile.
2. The patient supplies and verifies an email address through a single use link.
3. The system compares approved matching evidence and raises any conflict for receptionist or administrator review.
4. The reviewer checks the hospital’s approved identity evidence and either approves or rejects the claim.
5. Approval links one verified user to one patient profile, activates patient access, records consent where needed, and creates an audit event.
6. Rejection keeps the patient profile unclaimed and records a safe reason. It does not expose the profile to the requesting user.
7. Duplicate profiles require a separate governed correction process. The claim flow never merges their appointment or payment histories.

## 5. Staff invitation and authentication

### 5.1 Invite staff

1. An administrator enters the approved staff email, role, and expiry.
2. The system checks for an active account or invitation conflict.
3. The system stores only a digest of the single use invitation token and queues a privacy safe email.
4. The administrator’s action is audited.

### 5.2 Accept invitation

1. The invited person opens the link, confirms the invited email, sets a password, and accepts the staff privacy and access terms.
2. The person enrolls a TOTP authenticator and proves one valid code.
3. Recovery codes are shown once. Only their digests are stored.
4. The system activates the invited role and consumes the invitation.
5. Expired, revoked, used, or mismatched invitations are rejected safely.

### 5.3 Staff sign in

1. Staff enter email and password.
2. A correct first factor creates a short MFA challenge, not a complete staff session.
3. A valid TOTP code completes the session and rotates its identifier.
4. Failed password and MFA attempts are throttled and recorded without storing credentials or MFA secrets.
5. Role deactivation, password reset, MFA reset, or account deactivation revokes affected sessions under policy.

## 6. Hospital directory and schedule workflow

### 6.1 Configure hospital structure

1. An administrator configures the temporary or approved hospital branding, timezone, currency, contacts, departments, locations, and chambers.
2. The administrator creates or invites a doctor account and completes the approved public doctor profile.
3. A department, location, chamber, or doctor with business history is deactivated rather than deleted.
4. Public directory endpoints show only active approved fields.

### 6.2 Create a recurring schedule

1. The administrator selects one doctor, location, chamber, weekday, local start and end times, slot duration, capacity per slot, and effective date range.
2. The API rejects invalid time ranges, nonpositive duration or capacity, and overlaps for the same doctor or chamber.
3. The system stores the schedule and audit event in one transaction.
4. Availability is calculated from the active schedule only after the transaction commits.

### 6.3 Close or override a schedule

1. The administrator selects the schedule and affected date.
2. The administrator records a closure or approved replacement period, capacity, and reason.
3. The API checks existing confirmed appointments before applying a change that would remove capacity.
4. When confirmed appointments are affected, the system requires an explicit resolution workflow. It does not cancel patients silently.
5. The exception and audit event are committed together.
6. Affected staff views and patient availability refresh from the effective exception.

## 7. Appointment workflow

### 7.1 Find availability

1. A patient or receptionist selects an active department or doctor and an allowed date range.
2. The API expands the effective schedule, applies closures and overrides, excludes past times, and subtracts active confirmed capacity.
3. The API returns UTC slot boundaries with Asia/Dhaka display values and remaining availability, without exposing another appointment.
4. Availability is advisory until booking commits. The interface explains that a place can be taken by another request.

### 7.2 Book an appointment

1. A patient books for their own claimed profile. A receptionist may book for an authorized patient profile.
2. The user chooses the doctor, slot, and location, then reviews the exact time, timezone, fee, and cancellation information.
3. The write request carries an idempotency key.
4. The API validates ownership or reception authority and locks the relevant slot allocation.
5. Inside the transaction, the API recalculates the schedule, exception, remaining capacity, and time eligibility.
6. When capacity remains, the API creates the confirmed appointment, initial payment record, history, audit event, in app notification, and email outbox job.
7. When capacity is gone, the API returns a conflict and the interface refreshes availability. It never creates a partial or waiting appointment.
8. The confirmation shows the appointment details but does not create the final queue token.

### 7.3 Reschedule an appointment

1. The patient or receptionist opens an eligible confirmed future appointment.
2. The user selects and reviews a new available slot.
3. The API locks the appointment and old and new allocations in a stable order.
4. The API verifies the appointment remains confirmed and the new slot still has capacity.
5. Old capacity is released and new capacity is reserved in one transaction.
6. The appointment remains `confirmed`. Its history records both allocations, actor, time, and request identifier.
7. Notifications are created after the change is committed through the outbox.

### 7.4 Cancel an appointment

1. The patient or receptionist opens an eligible confirmed appointment and reviews the effect of cancellation.
2. The user confirms the action. Staff enter a reason when policy requires it.
3. The API locks the appointment, changes it from `confirmed` to `cancelled`, and releases capacity once.
4. If a queue ticket already exists, the authorized cancellation also moves that eligible ticket to `cancelled` and clears it as active where necessary.
5. History, audit, and notifications are committed with the change.
6. A repeated request returns the original idempotent result. It cannot release capacity twice.

### 7.5 Terminal appointment states

1. `confirmed` may become `cancelled`, `completed`, or `no_show`.
2. Rescheduling does not change `confirmed` status.
3. `cancelled`, `completed`, and `no_show` are terminal.
4. A later operational correction appends history and, where service is still needed, creates a replacement appointment. It never rewrites the terminal event silently.

## 8. Reception arrival workflow

### 8.1 Check in a booked patient

1. The receptionist locates today’s confirmed appointment through approved search.
2. The receptionist verifies the minimum identity fields and confirms the correct doctor, location, and queue session.
3. The API locks the appointment and queue session and checks that no active queue ticket already exists.
4. The API increments the queue token sequence and creates one `waiting` ticket.
5. The final privacy safe token, queue event, audit event, history, and notifications are committed together.
6. The receptionist gives the patient the token and explains how to view the live status.

### 8.2 Handle a walk in

1. The receptionist searches for the patient and creates an unclaimed profile only when necessary.
2. The receptionist selects an active doctor session that permits the walk in under the hospital’s capacity policy.
3. One idempotent service creates the confirmed appointment with source `walk_in`, the initial payment record, and the waiting queue ticket.
4. Capacity, token allocation, history, audit, and notifications commit together.
5. If capacity is unavailable, the receptionist offers an available appointment. The system does not insert the patient ahead of waiting patients.

### 8.3 Handle late arrival

1. A late patient may check in while the approved queue session remains open.
2. The ticket joins by actual check in time, not scheduled appointment time, so it does not pass patients already waiting.
3. If the doctor session is closed or the hospital cannot safely serve the patient, the receptionist follows the approved reschedule, cancellation, or no show workflow.
4. A manual exception requires an operational reason and appears in the fairness audit.

### 8.4 Duplicate check in

1. The API returns the existing active ticket for an identical idempotent request.
2. A different request for an appointment that already has an active ticket returns a conflict with the safe existing status.
3. The queue sequence is not incremented again.

## 9. Queue workflow

### 9.1 Queue order

1. An ordinary waiting ticket is ordered by effective waiting time, then token sequence as the stable tie breaker.
2. At first check in, effective waiting time equals check in time.
3. The system does not use age, sex, diagnosis, symptom, payment, influence, or predicted service duration to prioritize a patient.
4. A late arrival joins at the actual check in time.
5. A restored deferred ticket receives the restore time as its new effective waiting time. It joins behind tickets already waiting at that moment while the original check in time remains in the audit record.
6. An operational override may change the next selection only through an authorized action with a reason. The fairness record preserves the order before and after the override.

### 9.2 Call next

1. The doctor or authorized receptionist requests call next with an idempotency key.
2. The API locks the queue session and checks that no ticket is already `called` or `in_service`.
3. The API selects and locks the earliest eligible `waiting` ticket by the order in section 9.1.
4. The ticket changes from `waiting` to `called` and becomes the queue session’s active ticket.
5. The event, audit, estimate snapshot, in app notification, and email outbox job commit together.
6. A competing call next request returns the same idempotent result or a conflict. It cannot call a second patient.

### 9.3 Start service

1. The doctor confirms the called patient using the minimum approved identity fields.
2. The API locks the queue and ticket and verifies that the doctor owns the queue and the ticket is `called`.
3. The ticket changes to `in_service` and records `service_started_at`.
4. The queue event and audit event commit together.

### 9.4 Complete service

1. The doctor completes the `in_service` ticket.
2. The API records `service_ended_at`, changes the ticket to `completed`, and changes its confirmed appointment to `completed` in one transaction.
3. The queue session active ticket is cleared.
4. The service duration becomes an eligible Adaptive Arrival Window sample only when it passes the validity rules in `advanced_mechanism.md`.
5. Queue event, appointment history, estimate evaluation, audit, and notifications commit together.

### 9.5 Defer a patient

1. The doctor or authorized receptionist selects a `waiting` or `called` ticket and enters an operational reason.
2. The API changes the ticket to `deferred`, records the actor, time, reason, and previous effective order, and clears the active ticket when needed.
3. A deferred ticket is not selected by call next.
4. The patient sees that staff action is required but does not see internal notes or another patient’s information.

### 9.6 Restore a deferred patient

1. The doctor or authorized receptionist selects the deferred ticket and enters a reason for restoration.
2. The API changes the ticket from `deferred` to `waiting` and sets effective waiting time to the restore time.
3. The restored patient joins behind all patients already waiting. The original check in time and defer period remain visible in the authorized fairness record.
4. Any decision to place the patient elsewhere requires a separate operational override with a reason.

### 9.7 Mark no show

1. The doctor or authorized receptionist follows the hospital’s call and confirmation procedure outside the application.
2. The user selects an eligible `waiting`, `called`, or `deferred` ticket, enters a reason, and confirms the action.
3. The API changes the ticket and its confirmed appointment to `no_show`, clears the active ticket if needed, and commits history and audit.
4. `no_show` is terminal. A later return requires a new or rescheduled appointment according to hospital policy.

### 9.8 Cancel a queued visit

1. An authorized appointment cancellation may change an eligible `waiting`, `called`, or `deferred` ticket to `cancelled`.
2. The API clears the active ticket where needed and preserves all earlier queue events.
3. A ticket cannot be cancelled after service has started. The authorized correction process is used if an exceptional error is found.

### 9.9 Queue state summary

1. `waiting` may become `called`, `deferred`, `no_show`, or `cancelled`.
2. `called` may become `in_service`, `deferred`, `no_show`, or `cancelled`.
3. `in_service` may become `completed`.
4. `deferred` may become `waiting`, `no_show`, or `cancelled`.
5. `completed`, `no_show`, and `cancelled` are terminal.

## 10. Live patient queue workflow

1. The patient opens the queue route through an authenticated secure link or their appointment page.
2. The API verifies ownership and returns only the patient’s token, currently served token, people ahead, wait range, recommended return window, confidence label, last updated time, and connection guidance.
3. The response includes an `ETag`.
4. The visible page polls every 10 seconds. A hidden page polls every 30 seconds.
5. The browser sends `If-None-Match`; an unchanged snapshot returns `304 Not Modified`.
6. After 30 seconds without a successful response, the page marks the information stale and shows the last successful update.
7. When the browser is offline, polling pauses or fails safely, the page keeps the last safe snapshot, and it states that the patient should follow onsite staff guidance.
8. On reconnection, the page refreshes immediately and announces a meaningful status change to assistive technology without repeated noise.
9. No response names the currently served patient or lists other waiting patients.

## 11. Onsite payment workflow

### 11.1 Initial state

1. Every appointment receives one current payment record in `unpaid` state with an integer amount in BDT minor units.
2. The amount comes from approved configuration and is confirmed by authorized reception staff before collection.

### 11.2 Record payment onsite

1. The receptionist opens the correct appointment and verifies the patient and amount.
2. The receptionist records `paid_on_site` with an idempotency key and the approved collection reference when one exists.
3. The system commits the state, payment history, and audit event together.
4. The system never requests or stores card details.

### 11.3 Waive payment

1. An authorized receptionist or administrator selects `waived` from `unpaid` and enters the required reason.
2. The action records actor, time, old state, new state, amount, reason, and request identifier.

### 11.4 Refund or correct payment

1. An authorized user may change `paid_on_site` to `refunded` with a required reason and approved reference.
2. An authorized correction may return `waived` to `unpaid` before appointment completion and requires a reason.
3. `refunded` is terminal. A later collection creates a separately approved payment record and does not rewrite the refund.
4. Amount corrections append payment history and remain reconcilable from the original value.

## 12. Notification workflow

1. The business service creates an in app notification and email outbox job in the same transaction as the appointment, queue, security, or consent event.
2. Before sending an account verification, reset, claim, or staff invitation message, the worker confirms that its single use token is still active. Expired, consumed, or superseded links are discarded and their sensitive template data are cleared.
3. The worker claims eligible outbox rows with a PostgreSQL row lock and a bounded lease.
4. The worker renders only an approved versioned template and sends through production SMTP.
5. Success records delivery time and safe provider reference.
6. A temporary failure records a safe error category and schedules a bounded exponential retry with jitter.
7. A permanent or exhausted failure becomes terminal, appears in administrator operations, and raises an alert.
8. An authorized manual retry creates an audited attempt and cannot alter the original business event.
9. Email contains minimal operational content and a secure link. It does not contain symptoms, specialty, another patient’s data, credentials, or detailed audit content.

## 13. Correction and deactivation workflow

1. The authorized user opens the current record through a named correction action.
2. The interface shows the current value, proposed value, effect, and required reason.
3. The API verifies role, object scope, state eligibility, and whether a second approver is required by hospital policy.
4. The API appends history and an audit event with old and new values. It does not update an earlier history or audit row.
5. Doctors, patients, schedules, departments, locations, chambers, and staff with history are deactivated rather than hard deleted.
6. A mistaken duplicate patient record is contained and referred to the approved identity correction process. Automatic merge is forbidden in the pilot.

## 14. Incident escalation workflow

### 14.1 Identify and contain

1. The person who notices a security, privacy, availability, data integrity, queue safety, or notification problem records the time, affected function, safe evidence, and current impact.
2. A suspected critical issue is reported immediately to the delivery lead, operations owner, hospital administrator, and security and privacy reviewer.
3. Operations preserves logs and audit evidence, restricts affected access, revokes compromised sessions or credentials, and isolates a service only as needed to limit harm.
4. Staff move to the hospital’s approved manual appointment and queue procedure when the system cannot be trusted.
5. No one deletes records, rotates away evidence, or sends patient details through an unapproved channel during investigation.

### 14.2 Classify and communicate

1. Critical means active unauthorized access, credible sensitive data exposure, unrecoverable corruption, unsafe queue operation, or complete production outage without a safe fallback.
2. High means a serious control failure or major workflow outage with limited current impact and a viable containment.
3. Medium means material but bounded incorrect behavior with a safe workaround.
4. Low means a minor defect with no material security, privacy, data integrity, or critical workflow effect.
5. The incident owner sets update intervals and uses approved contacts. Patient or regulator communication follows hospital and qualified legal guidance.

### 14.3 Recover and learn

1. Recovery uses the documented rollback or restore procedure and validates database integrity before reopening access.
2. Critical workflows are smoke tested with synthetic data before service resumes.
3. The incident record states cause, timeline, affected records, containment, recovery, notification decision, and corrective tasks.
4. Regression tests and documentation are updated before the corrective change is considered complete.

## 15. Git change workflow

### 15.1 Repository controls

1. The repository is private and has no public open source license by default.
2. `main` is protected and represents reviewed releasable work.
3. Supplied PDFs, screenshots, signatures, secrets, local environment files, database dumps, production data, uploads, local certificates, and generated private reports stay outside Git.
4. Private container images are stored in the approved private GitHub Container Registry package.
5. Production and staging deployments use protected GitHub environments with named approval.

### 15.2 Start a change

1. Create one short lived branch from current `main` using `feature/`, `fix/`, `docs/`, or `ops/` followed by a clear lowercase name.
2. Link the branch to one task or defect with acceptance conditions.
3. Rebase or merge current `main` according to the repository policy before requesting final review.
4. Never place a secret or real patient data in a branch, commit, test fixture, screenshot, log, or pull request discussion.

### 15.3 Build and verify a change

1. Keep each commit focused and use a short human readable message that describes the result.
2. Add or update tests with behavior changes.
3. Update `implementation_plan.md`, `workflow.md`, `production.md`, `test.md`, `audit.md`, `bugs.md`, or `advanced_mechanism.md` when their contract changes.
4. Run relevant local checks before pushing.
5. CI performs formatting checks, lint, unit and API tests, migration checks, frontend tests, production builds, dependency checks, and approved security scans.

### 15.4 Review and merge

1. The pull request explains the problem, implemented behavior, risk, migration effect, security and privacy effect, tests, manual evidence, and rollback consideration.
2. A reviewer checks authorization, transactions, state changes, privacy projection, errors, accessibility, test strength, and documentation consistency.
3. A database migration receives an operations review. An authorization, authentication, audit, queue fairness, payment, or consent change receives a security and privacy review.
4. Required CI and review must pass before merge.
5. Merge through the protected repository control. Direct pushes and force pushes to `main` are not allowed.

## 16. Release workflow

### 16.1 Prepare the production candidate

1. Select one reviewed commit from `main` and build immutable application artifacts in CI.
2. Record artifact digests, exact dependencies, migration set, configuration changes, test evidence, known limits, and unresolved nonblocking risks.
3. Promote the same artifacts to staging. Do not rebuild different artifacts for production.
4. Apply migrations through the documented deployment command and run readiness and browser smoke checks.
5. Run doctor and receptionist UAT on the exact staged revision with synthetic data.

### 16.2 Approve and tag

1. The delivery lead confirms all release checks and blocking defect closures.
2. Operations confirms backup, restore, monitoring, alerts, migration, and rollback evidence.
3. Hospital representatives sign the critical workflows.
4. Security and privacy review confirms there is no unresolved critical or high finding.
5. The release is tagged as a production candidate, for example `v0.1.0-rc.1`, and the tag points to the tested artifacts.

### 16.3 Deploy or hold

1. Staging deployment may proceed when its infrastructure and approvals are available.
2. Real patient data deployment proceeds only when every real data launch gate is approved in writing.
3. If any gate is missing, the release remains a synthetic data production candidate. The release record names the missing gate and owner.

### 16.4 Production deployment

1. Confirm the latest encrypted backup and restore evidence before the change window.
2. Put the release artifacts and configuration in place without exposing secrets.
3. Run compatible database migrations.
4. Start or reload services, then verify liveness, readiness, database access, outbox processing, TLS, logs, and monitoring.
5. Run the approved production smoke checks with designated test records.
6. Announce completion through the approved hospital channel and monitor closely through the agreed observation period.

### 16.5 Rollback

1. Stop promotion when health, migration, authorization, data integrity, or critical workflow checks fail.
2. Roll back application artifacts when the schema remains backward compatible.
3. Use the migration specific recovery decision when schema rollback is safe and tested.
4. Restore from the verified backup when data integrity cannot be recovered safely through forward correction.
5. Record the decision, timeline, data effect, checks, and follow up defect.

## 17. Documentation workflow

1. The delivery lead owns cross document consistency.
2. A behavior change updates its implementation contract and operational workflow in the same pull request.
3. A new defect or accepted limitation updates `bugs.md`.
4. A test change updates `test.md` with its pass condition and evidence location.
5. An infrastructure, recovery, or monitoring change updates `production.md`.
6. A permission, threat, privacy, citation, or requirement decision updates `audit.md`.
7. A queue estimate or fairness rule change updates `advanced_mechanism.md`, its fixed test vectors, and its calculation version.
8. The release review checks dates, roles, states, route names, thresholds, and exclusions across all planning files before tagging.
