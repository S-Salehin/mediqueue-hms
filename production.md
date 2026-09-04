# Production Operations Guide

Document status: Production candidate baseline

Last reviewed: 14 August 2026

System codename: MediQueue

## 1. Purpose and release boundary

This guide defines how the hospital operations and adaptive queue system will be configured, deployed, monitored, backed up, restored, and supported. It applies to local development, continuous integration, staging, and production.

The first production candidate covers appointments, reception, queues, onsite payment records, notifications, consent, and operational audit records for one small hospital. It does not contain clinical notes, diagnoses, prescriptions, test results, insurance records, card information, or automated medical prioritisation.

Synthetic data is mandatory until every real data launch gate in section 16 has written approval. A successful software deployment is not permission to enter patient data.

## 2. Service objectives

The pilot is designed for up to 30 doctors, 500 appointments in one day, and 50 concurrent users.

1. Monthly availability target is 99.5 percent, excluding approved maintenance announced at least 24 hours in advance.
2. Recovery point objective is one hour.
3. Recovery time objective is four hours from declaration of a service incident.
4. At the expected load, the 95th percentile response time must remain below 500 milliseconds for read requests and 800 milliseconds for write requests.
5. The five minute server error rate must remain below 1 percent during normal operation.
6. A connected queue screen must show data no more than 15 seconds behind the latest committed queue event.
7. A privacy safe email should leave the notification outbox within two minutes during normal operation.

The availability calculation uses successful responses from the public readiness endpoint at one minute intervals. Planned maintenance counts against the objective if it was not announced or exceeds its approved window.

## 3. Environment model

### 3.1 Local development

Local development uses Docker Compose with the application and PostgreSQL 18. PostgreSQL is required in local development because transactions, row locks, indexes, and constraints are part of core booking and queue behaviour. SQLite is not an accepted substitute.

Local email is captured by a development mail service and must not be delivered to public addresses. Seed commands create synthetic doctors, patients, schedules, appointments, and queues. Developers must not copy production data into a workstation.

Local secrets belong in an ignored environment file. The committed example file contains names and safe explanations, never working credentials.

### 3.2 Continuous integration

Every pull request receives an isolated PostgreSQL 18 database and disposable application environment. Continuous integration installs exact locked dependencies, applies all migrations to an empty database, runs backend and frontend tests, builds the frontend and container image, and performs dependency and secret scans.

The continuous integration environment uses generated credentials and synthetic fixtures. Artifacts may contain test reports, coverage, and scan results, but must not contain environment files, database dumps, or user submitted documents.

### 3.3 Staging

Staging mirrors production versions, reverse proxy rules, database extensions, worker behaviour, security headers, and environment settings. Its hostname and credentials are separate from production. Staging uses synthetic data and a nonproduction email domain or an address allowlist.

Every release candidate must remain healthy in staging while the smoke test, migration check, browser test, permission test, and load test are completed. A staging database is never promoted into production.

### 3.4 Production

Production runs only signed or traceable images built from the protected main branch. Debug mode is disabled. Source maps are not publicly served. Production email is enabled only after the hospital approves the sender domain and privacy safe templates.

SMTP connections use the bounded `SMTP_TIMEOUT_SECONDS` setting. The default is 10 seconds and accepted values are from 1 through 60 seconds. A slow or unavailable mail server cannot hold the worker indefinitely, and notification retries never reverse a committed hospital action.

The production database is used only by the application, worker, backup job, and authorised database administrator. Direct changes through a database console are prohibited except during an approved incident procedure, and every emergency correction must be documented in the incident record.

## 4. Production host and network

The minimum pilot host is a Bangladesh based virtual private server with 4 virtual CPUs, 8 GiB memory, 160 GiB NVMe storage, and Ubuntu 24.04 LTS. The provider must offer console access, storage monitoring, and a documented hardware incident process.

1. The public firewall permits TCP 80 and 443. Port 80 exists only for certificate validation and redirecting to HTTPS.
2. SSH is restricted to named administrator addresses where practical. It uses keys only, disables direct root login, and is protected by rate limiting.
3. PostgreSQL has no published host port and listens only on the private Compose network.
4. The host clock synchronises with a trusted time source. All stored timestamps use UTC. User interfaces display Asia/Dhaka time.
5. Automatic operating system security updates are enabled. Updates that require restart are installed in an announced maintenance window.
6. Only named production operators receive host access. Shared accounts and shared SSH keys are prohibited.

The production DNS record points only to the approved host. Caddy obtains and renews the TLS certificate. Certificate expiry is monitored externally. HTTP Strict Transport Security is enabled only after HTTPS operation has been verified on the final domain.

## 5. Docker production topology

The production Compose project contains the following long running services.

1. `caddy` uses the immutable web image for the release. It terminates TLS, serves the built React application, routes `/api/v1/` and operational health requests to the API, adds approved security headers, and writes access logs without query strings.
2. `api` runs Django through Gunicorn with a conservative worker count based on the available memory. It exposes no public port and becomes ready only after its database check succeeds.
3. `worker` processes the database backed notification outbox. It uses the same immutable application image as the API and has no inbound public route.
4. `db` runs PostgreSQL 18 on a named volume and the private network. It has a health check and a fixed major version.
5. `backup` runs pgBackRest for scheduled encrypted database backups, write ahead log archiving, and archive validation. It has read access only to the backup configuration and the database credentials required for backup.

Each service has a memory limit, restart policy, health check, and log size policy. Caddy depends on API health, not only container startup. The API and worker run as an unprivileged user with a read only application filesystem and writable temporary directories only where required.

The database volume, Caddy data, and backup cache are the only persistent service data. Application containers are replaceable. No uploaded clinical files are part of this release.

## 6. Configuration and secret control

Production configuration is stored outside Git in `/etc/mediqueue/production.env`, owned by root and readable only by the deployment account and authorised services. The Compose file refers to values by name. It never contains a working password.

Required application and deployment secrets include the Django secret key, separate MFA encryption key, three PostgreSQL role passwords, SMTP credentials, backup encryption key, and private registry read token. Credentials for off host replication and alert delivery belong in their separately approved operator services, not in the application environment file. Required nonsecret settings include the public origin, trusted proxy settings, timezone, sender address, hospital identity, support contact, session duration, and privacy notice version.

1. Secrets must be randomly generated and unique to each environment.
2. Logs, error pages, health endpoints, build output, and support screenshots must never print a secret.
3. Production secrets are shared through the hospital approved password manager, not email or chat.
4. The Django secret key and database password are rotated after suspected exposure and during the annual access review.
5. SMTP and monitoring credentials are scoped to the minimum required permissions.
6. Backup credentials allow access only to the dedicated encrypted repository.
7. Departing operators have access removed on their final working day or immediately when risk requires it.

`REAL_DATA_APPROVED` remains false until all launch evidence is signed. `OFF_HOST_BACKUP_APPROVED` remains false until the separate encrypted copy is configured and a restore from that copy succeeds. Production validation requires both values before real patient data is permitted.

The deployment operator compares the required setting names with the committed example before every release. Missing, blank, development, or placeholder values cause startup to fail.

## 7. Image build and release records

Continuous integration builds one application image for the API and worker and one web image containing Caddy and the immutable frontend assets. Both images come from the same reviewed commit, carry the full Git commit identifier, and are stored in the private GitHub Container Registry. A mutable `latest` tag is not used for production deployment.

The release record contains:

1. Git commit identifier and release tag.
2. Exact application and web image digests.
3. Database migration list.
4. Test, dependency scan, container scan, and staging smoke test results.
5. Operator name, deployment time, and hospital approver.
6. Known low risk defects and the approved response.
7. Previous known good image digest and rollback notes.

Only the protected production environment in GitHub Actions may use the production deployment credentials. Production deployment requires manual approval by a named maintainer who did not author the final change where staffing permits.

## 8. Database migration policy

Every schema change is represented by a reviewed Django migration. Hand edited production schemas are prohibited.

1. A new release must apply successfully to an empty PostgreSQL 18 database and a copy of the current staging schema.
2. Data migrations must be deterministic, restartable where possible, and tested with realistic row counts.
3. Large data updates run in bounded batches and report progress. They must not hold a table lock across the full dataset.
4. Destructive changes use an expand and contract sequence. A release first adds the replacement column or table and supports both forms. A later release removes the old form after verification and backup retention.
5. A migration that cannot safely reverse must state this in its source and release record. Its rollback is a forward repair or database restore, never an improvised reverse command.
6. Migrations do not create administrators, real patients, or default passwords.
7. The deployment takes and verifies a fresh recovery point before applying production migrations.

The API image and migration set are treated as one release. An older image must not be started against an incompatible schema.

## 9. Standard deployment procedure

The deployment operator completes these actions in order.

1. Confirm that the release commit is reviewed, continuous integration is green, the image digest is recorded, and no critical or high security finding is open.
2. Deploy the exact image to staging, apply migrations, and complete the release smoke tests.
3. Confirm the approved maintenance window, operator contacts, external monitor maintenance state, previous image digest, and rollback owner.
4. Verify the latest scheduled backup and create a fresh recovery point. Record the successful validation result.
5. Pull both production images by digest without changing the running services.
6. Run Django deployment checks and show the migration plan. Stop if an unexpected migration appears.
7. Apply migrations once from a one time container. Stop if any migration fails.
8. Replace the worker, API, and Caddy services with the approved release. Wait for health checks before removing the previous containers.
9. Run production smoke tests using dedicated test accounts and records clearly marked as synthetic.
10. Verify login, staff MFA, public directory, one synthetic booking, reception check in, queue snapshot, notification outbox, audit event, and logout.
11. Check error rate, response time, worker age, disk use, and database connections for at least 15 minutes.
12. End the maintenance state, record the result, and notify the hospital release contact.

The operator stops the deployment on migration failure, readiness failure, unexpected permission behaviour, notification duplication, elevated error rate, or inability to restore the prior service safely.

## 10. Rollback procedure

Rollback is declared when the release causes a security defect, data integrity risk, unavailable critical workflow, sustained service objective breach, or failed smoke test that cannot be corrected safely within the maintenance window.

1. Pause new deployments and record the incident start time.
2. If writes could worsen data damage, place the system in maintenance mode while preserving operator access.
3. Identify whether the database schema remains compatible with the previous image.
4. When compatible, start the recorded previous image digest, keep the current database, and repeat the readiness and smoke checks.
5. When incompatible, follow the migration release note. Use a reviewed reverse migration only when it was tested before release.
6. When neither image rollback nor reviewed reverse migration is safe, restore the verified predeployment recovery point into a clean database volume and point the known good image to it.
7. Reconcile any valid appointments or queue events created after the recovery point using the audit record and the approved downtime log. Never recreate records from memory.
8. Confirm monitoring, reopen the service, notify the hospital contact, and begin a written incident review.

An operator never deletes a failed database or backup during rollback. It remains isolated until evidence collection and reconciliation are complete.

## 11. Monitoring and alerting

The application exposes separate liveness and readiness endpoints. Liveness confirms that the process can answer. Readiness confirms that required configuration is valid and PostgreSQL can accept a simple query. Neither endpoint returns versions, secrets, record counts, or patient information.

Application logs are structured and include UTC time, severity, service, event name, request identifier, route template, status, and duration. They do not include passwords, session identifiers, CSRF tokens, email bodies, patient names, phone numbers, appointment notes, raw request bodies, or URL query strings.

The deployment must provide the following views:

1. External HTTPS availability and certificate expiry.
2. Read and write response time percentiles, request volume, and status groups.
3. Database availability, connections, slow queries, volume use, and backup age.
4. Notification outbox depth, oldest pending item, retry count, and permanent failure count.
5. Queue snapshot age and failed polling responses.
6. Host CPU, memory, disk use, inode use, restart count, and clock health.
7. Administrative authentication failures and account lockouts without exposing credentials.

Alerts are sent to at least two named operators and the hospital technical contact. Critical alerts require acknowledgement.

1. External readiness failure for two consecutive minutes is critical.
2. Database unavailable or unable to accept writes is critical.
3. Disk use above 90 percent is critical. Above 80 percent is a warning.
4. Five minute server error rate above 5 percent is critical. Above 1 percent for 15 minutes is a warning.
5. The oldest ready notification older than five minutes is a warning and older than fifteen minutes is critical.
6. Queue data older than 30 seconds for five consecutive checks is a warning.
7. Missing hourly recovery point, failed daily backup, failed archive validation, or certificate expiry within 14 days is critical.
8. Repeated staff authentication failures from one source or against one account trigger a security warning.

Alert delivery itself is tested monthly. A monitor that cannot reach its alert destination is considered failed.

## 12. Backup policy

PostgreSQL backup uses pgBackRest with a dedicated encrypted repository. The locked pgBackRest release and its container image must pass the restore test with PostgreSQL 18 before production use.

1. A full encrypted backup runs daily at 01:30 Asia/Dhaka.
2. An incremental recovery point runs every hour.
3. Write ahead log archiving runs continuously so that recovery can select a safe time within the one hour objective.
4. Backup content is encrypted before transfer with the pgBackRest repository cipher. Its cipher key is held separately from the repository credentials.
5. One copy remains on approved separate infrastructure. The production host is not the only location.
6. Daily and hourly recovery material is retained for 30 days. Monthly archival retention requires separate hospital and legal approval.
7. Backup jobs verify archive continuity and database manifest integrity after completion.
8. The backup repository must deny public access and use a credential that cannot administer the production server.

Database backups contain personal information once the system is live. Access is limited to named database and incident operators. Downloads to personal computers and unencrypted removable media are prohibited.

## 13. Restore procedure

A clean restore test is completed before real data launch, monthly during the pilot, and after any backup tool or PostgreSQL version change.

1. Declare the restore purpose, selected recovery time, operator, and isolated target environment.
2. Provision a clean PostgreSQL 18 volume with no connection from the public application.
3. Retrieve the required backup and archive records using the dedicated restore credential.
4. Decrypt and restore to the selected time. Preserve the source backup unchanged.
5. Start PostgreSQL and run consistency checks, migration state checks, and critical table counts.
6. Start the matching application image against the isolated database.
7. Verify synthetic or controlled records across users, schedules, appointments, queue events, payments, notifications, consent, and audit events.
8. Confirm that a sampled appointment history and queue history retain their order and relationships.
9. Record elapsed time, newest restored transaction time, data gap, warnings, and final result.
10. Destroy the isolated restored copy through the approved secure disposal procedure after evidence is retained.

The test passes only when the data gap is no more than one hour, usable service is restored within four hours, integrity checks pass, and no unexpected external email or webhook is sent.

## 14. Incident response

Anyone who observes an outage, data integrity defect, suspected unauthorised access, exposed secret, privacy disclosure, or repeated operational failure must open an incident record immediately.

### 14.1 Severity

1. Severity 1 covers confirmed or likely personal data exposure, active compromise, unrecoverable corruption, total critical service loss, or patient safety risk. The first operator acknowledges within 15 minutes and contacts the hospital incident lead immediately.
2. Severity 2 covers a critical workflow unavailable without a safe workaround, sustained performance failure, failed recent backups, or incorrect permissions with no confirmed disclosure. Acknowledgement target is 30 minutes.
3. Severity 3 covers a degraded noncritical function with a safe workaround. Acknowledgement target is four working hours.
4. Severity 4 covers minor defects and documentation issues. These enter the normal backlog.

### 14.2 Response flow

1. Record facts, UTC and local time, reporter, affected functions, and known users. Do not speculate in the factual timeline.
2. Contain the issue by disabling the affected account, feature, integration, or network route when doing so reduces harm.
3. Preserve relevant logs, image digests, database snapshots, audit records, and access records. Do not edit original evidence.
4. Recover through the documented rollback or restore procedure.
5. Validate permissions, data integrity, notifications, and monitoring before reopening service.
6. The hospital incident lead decides legal, regulator, and patient notification with qualified counsel. Developers do not make unsupported notification claims.
7. Complete a review within three working days for Severity 1 or 2. Record cause, contributing conditions, impact, response quality, corrective owner, and due date.

During downtime, reception uses the approved numbered paper log. It contains only the minimum information required to continue appointments. Two staff members reconcile it after recovery, and the paper is stored or destroyed under the hospital retention policy.

## 15. Routine operations

The operator checks readiness, open critical alerts, notification delay, database capacity, disk use, and last recovery point every working day. Failed jobs are investigated the same day.

Each week, the operator reviews account lockouts, unusual staff access, failed notifications, queue overrides, database growth, dependency advisories, and expiring certificates.

Each month, the team completes a clean restore exercise, alert delivery test, staff access review, operating system patch window, audit event sample, and service objective report. The hospital owner reviews repeated queue overrides and prediction errors as operational quality issues, not clinical conclusions.

At least annually, or sooner after material change, the hospital reviews retention, access roles, incident contacts, privacy notice, consent wording, backup access, vendors, and legal obligations.

## 16. Real data launch gates

Production may use synthetic demonstration data before these gates pass. It must not accept real patient data until evidence for every item is stored in the release record.

1. A Bangladesh based host, final domain, DNS, TLS, production SMTP service, and separate encrypted backup storage are purchased and configured.
2. The hospital approves its final name, logo, address, contact details, operational owner, privacy contact, support route, privacy notice, consent wording, retention schedule, access policy, and incident process.
3. A qualified reviewer maps the deployed system and operating procedures to the applicable Bangladesh Personal Data Protection Act 2026, National Data Management Act 2026, Cyber Security Act 2026, healthcare duties, employment duties, and any regulator guidance then in force.
4. The legal review states where data may be hosted and backed up, which vendors may process it, how access requests and corrections are handled, how long each record is retained, and when an incident requires notification.
5. A hospital doctor and receptionist complete and sign the critical workflow acceptance list using staging.
6. Every staff account belongs to a named person, has the correct role, uses multifactor authentication, and appears in the approved access register.
7. Staff training covers patient identity checking, privacy safe queue use, correction, downtime, onsite payment recording, and incident escalation.
8. The release has no unresolved critical or high security findings and no open Severity 1 or Severity 2 defect.
9. A clean backup restore, deployment rollback rehearsal, monitoring alert test, and notification failure test meet the stated objectives.
10. Production support contacts, escalation order, maintenance window, and downtime forms are available to staff.
11. A controlled pilot in one department succeeds before access is extended to the rest of the hospital.

Legal review and hospital approval are operational dependencies. This guide does not replace legal advice, clinical governance, or a signed data processing agreement.

## 17. Pilot launch and expansion

The first live pilot is limited to one department, a named doctor group, trained reception staff, and a written start and end date. The hospital appoints one person who may pause the pilot.

During the pilot, the team reviews booking conflicts, check in failures, queue freshness, wait range accuracy, override reasons, notification delay, support requests, and privacy incidents each day. Expansion requires three consecutive operating days with no Severity 1 or Severity 2 defect, successful end of day reconciliation, acceptable queue freshness, and signed approval from the hospital owner.

If the pilot must stop, reception returns to the approved downtime workflow. Existing records remain available to authorised staff for reconciliation and are not silently deleted.

## 18. Production acceptance record

The final acceptance record must identify the release, environment, approvers, evidence links, approved exceptions, pilot boundary, support period, and next review date. Signoff is required from the technical owner, hospital operational owner, doctor representative, receptionist representative, privacy or legal reviewer, and deployment operator.

## Help assistant operations

The assistant is designed to remain useful without an external language provider. `GROQ_API_KEY` may be empty. When it is empty or Groq is unavailable, controlled local answers and live database calculations continue normally.

If Groq is enabled, its key is an application secret stored only in the protected environment file. It must be rotated after suspected exposure and must never appear in logs, screenshots, support records, source code, or deployment output. Provider failures are logged by error class only. Prompt text is not logged.

Real patient use of Groq requires written approval of the provider relationship by the hospital and privacy reviewer. The review must cover purpose, data fields, geographic processing, retention, training use, subcontractors, access, incident notification, deletion, contract terms, and the method used to disable the integration. Until that review is accepted, production keeps `GROQ_API_KEY` empty.

The protected production environment records this decision as `GROQ_PROCESSOR_APPROVED`. Deployment validation rejects a configured Groq key when real data is approved but the processor decision remains false.

Monitoring records assistant request rate, local fallback rate, provider availability, response latency, and refusal checks without retaining question text. An assistant outage never blocks authentication, appointments, check in, queue operation, payment recording, notifications, or administration.

An exception must name its risk, temporary control, owner, deadline, and approval. Critical security, privacy, integrity, backup, or access control gates cannot be waived for real data launch.
