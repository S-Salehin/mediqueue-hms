# MediQueue hospital operations pilot

MediQueue is the development name for a hospital appointment, reception, and live queue system. It is built for one small hospital with up to 30 doctors, 500 appointments in a day, and 50 concurrent users.

The project is a production candidate and a university final year project. It is not an electronic medical record. It does not store diagnoses, prescriptions, clinical notes, test results, card details, or automated triage decisions.

## Current release status

The repository contains the assembled production candidate. Development and staging must use synthetic data while the automated release evidence, hospital acceptance, infrastructure, and legal launch gates are completed.

A working build does not authorize real patient data. The hospital, technical owner, legal or privacy reviewer, doctor representative, receptionist representative, and deployment operator must approve every launch gate in [production.md](production.md) before a real data pilot begins.

MediQueue is a temporary codename. The hospital name, logo, contact details, sender identity, privacy notice, and support route must be approved and configured before public use.

## What the pilot covers

1. Patient registration and generated medical record numbers.
2. Doctor, department, chamber, schedule, closure, and capacity management.
3. Appointment booking, rescheduling, cancellation, check in, and walk ins.
4. Privacy safe queue tokens and live queue progress.
5. Estimated wait ranges and recommended arrival windows without clinical prioritisation.
6. In application notifications and minimal email notifications.
7. Onsite payment records in BDT without online card processing.
8. Patient, doctor, receptionist, and administrator workspaces.
9. Consent records, business audit events, health checks, backups, and recovery procedures.

Clinical care records, laboratory, pharmacy, beds, insurance, inventory, payroll, online payments, SMS, AI diagnosis, and multi hospital tenancy are outside this release.

## Technology

The browser application uses React 19.2.8, JavaScript, Vite 8.2.1, Tailwind CSS 4.3.3, and an accessible custom component layer. The API uses Python 3.14.7, Django 5.2.17 LTS, and Django REST Framework. PostgreSQL 18.6 is the only supported database. Node.js 24.19.0 builds the browser assets and Caddy 2.11.4 serves them.

Caddy serves the built browser application and sends `/api/v1/` requests to Django on the same origin. Gunicorn runs the API in staging and production. A separate Django process handles the database notification outbox. Queue pages use conditional polling, so Redis and WebSockets are not required for this pilot.

Python and JavaScript dependency graphs are exact pinned in committed requirement and package lock files. Base images and verification runners use immutable digests. GitHub Actions use reviewed commit identifiers. Release containers carry the Git commit identifier, are scanned with their operating system libraries, include an SBOM, and are published by immutable digest.

## Repository guide

| Location | Purpose |
| --- | --- |
| `backend/` | Django API, data model, services, worker, and backend tests |
| `frontend/` | React interface, browser state, queue polling, and frontend tests |
| `infra/` | Container images, Caddy policy, backup configuration, and systemd timers |
| `scripts/` | Guarded deployment, backup, restore, rollback, and smoke procedures |
| `.github/` | Continuous integration, security review, release images, deployment controls, and review templates |
| `implementation_plan.md` | Architecture, interfaces, state rules, and implementation boundary |
| `workflow.md` | Hospital and engineering workflows |
| `audit.md` | Source traceability, risk decisions, and permission analysis |
| `test.md` | Acceptance evidence and release test requirements |
| `production.md` | Deployment, monitoring, incident, backup, restore, and launch policy |
| `advanced_mechanism.md` | Adaptive Arrival Window and Fairness Audit design |

The supplied university PDFs and interface references are deliberately ignored by Git because they contain raw scans, signatures, or source material that does not belong in the private code history.

## Local setup with Docker

Docker Desktop or Docker Engine with Compose v2 is the supported local path. PostgreSQL is not published to the host.

1. Copy the local configuration template.

   PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   Bash:

   ```bash
   cp .env.example .env
   ```

2. Replace the bootstrap, migration, runtime, and Django passwords in `.env`. Keep each value different. Update `DATABASE_URL` and `MIGRATION_DATABASE_URL` with their matching URL encoded passwords. Local debug mode can leave `MFA_ENCRYPTION_KEY` blank, but a separate value is recommended when testing staff MFA.

3. Build and start the local services.

   ```bash
   docker compose --env-file .env up --build --wait
   ```

4. Open the application at `http://localhost:8080`.

5. Open the development email inbox at `http://localhost:8025`. Mailpit is bound to the local computer and never sends mail to public addresses.

6. Choose the data setup for this local database. For a full demonstration, create the deterministic synthetic dataset.

   ```bash
   docker compose --env-file .env exec api python manage.py seed_synthetic
   ```

   This creates the demonstration hospital, an active demonstration privacy notice, directory records, appointments, and labelled staff accounts. It refuses to run over an existing hospital.

   For a clean configuration without demonstration records, create the hospital instead.

   ```bash
   docker compose --env-file .env exec api python manage.py bootstrap_hospital \
     --name "Local Hospital" \
     --short-name "LH"
   ```

7. On a clean configuration, create the first application administrator. The command prompts for a strong password and prints one TOTP enrollment URI to the current terminal. Enroll it immediately and do not copy it into logs, chat, or screenshots.

   ```bash
   docker compose --env-file .env exec api python manage.py bootstrap_admin \
     --email admin@example.test \
     --display-name "Development Administrator"
   ```

   Sign in with MFA, open the administrator privacy notice page, and publish the exact approved local test notice. Patient registration deliberately remains unavailable until one notice is active. The API used by that page is `/api/v1/admin/privacy-notices/`.

8. Stop the services without deleting the local database.

   ```bash
   docker compose --env-file .env down
   ```

Use `docker compose --env-file .env down --volumes` only when the local synthetic database and captured development mail are no longer needed. That command permanently removes those local project volumes.

The application API is available only through Caddy at the same origin. Direct database and API ports are not exposed.

## Local development commands

Run a Django check:

```bash
docker compose --env-file .env exec api python manage.py check
```

Review migration state:

```bash
docker compose --env-file .env exec api python manage.py showmigrations
docker compose --env-file .env exec api python manage.py makemigrations --check --dry-run
```

Process the notification outbox once while diagnosing delivery:

```bash
docker compose --env-file .env exec api python manage.py process_outbox --once
```

Follow service logs:

```bash
docker compose --env-file .env logs --follow api worker caddy
```

Do not paste logs into issues before checking them for personal data, cookies, email content, credentials, and request bodies.

## Tests

Backend acceptance tests require PostgreSQL 18. SQLite is not supported, even for tests that appear unrelated to locking.

Run the backend coverage suite in its disposable Compose environment:

```bash
docker compose --env-file .env.test.example --file compose.test.yml --profile tests run --rm --build backend-tests
```

Run frontend lint, tests, and the production build on the host:

```bash
cd frontend
npm ci
npm run lint
npm run test:coverage
npm run build
```

Run the critical Chromium workflows against a fresh same origin test stack:

```bash
docker compose --env-file .env.test.example --file compose.test.yml up --build --detach --wait db api worker web
docker compose --env-file .env.test.example --file compose.test.yml exec --no-TTY --env DJANGO_DEBUG=true api python manage.py seed_synthetic --doctors 3 --appointments 6
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
cd ..
docker compose --env-file .env.test.example --file compose.test.yml down --volumes --remove-orphans
```

These tests use only the deterministic `example.test` records. They cover public and privacy pages, patient availability, staff MFA, receptionist check in, the patient queue projection, and the assigned doctor queue. Always remove the disposable volumes after the run.

## Pilot load check

The reproducible k6 scenario is a quick local read gate. It ramps to 50 virtual users against same origin public reads, holds that level for 60 seconds, then ramps down. It fails when read p95 reaches 500 milliseconds or the checked response error rate reaches 1 percent. The pinned runner is part of the disposable test Compose file.

Start the test stack, then run the scenario:

```bash
docker compose --env-file .env.test.example --file compose.test.yml up --build --wait db api worker web
docker compose --env-file .env.test.example --file compose.test.yml --profile performance run --rm load-test
```

To include a privacy safe authenticated queue snapshot, supply the queue session UUID and the complete Django session cookie header value through the process environment. Use a synthetic account and clear the values from the terminal session afterward.

```bash
QUEUE_ID=00000000-0000-0000-0000-000000000000 \
DJANGO_SESSION_COOKIE='sessionid=synthetic-session-value' \
docker compose --env-file .env.test.example --file compose.test.yml --profile performance run --rm load-test
```

Do not run this check against production as routine verification. The script rejects a production target unless the separately approved process supplies `TARGET_ENV=production` and the exact `LOAD_TEST_APPROVAL=PRODUCTION:hostname` confirmation. A remote staging target must contain synthetic data and requires its matching `SYNTHETIC:hostname` approval. Save the k6 summary with the release evidence.

This quick gate does not exercise booking, check in, queue transitions, payment writes, queue freshness, notification recovery, or the 800 millisecond write target. It therefore does not establish production capacity and cannot close the full load release gate. The separate 30 minute authenticated mixed workload in `test.md` must run on production sized staging with independent synthetic records and operational monitoring before real data approval.

Start the built test stack and verify same origin routing:

```bash
docker compose --env-file .env.test.example --file compose.test.yml up --build --wait db api worker web
curl --fail http://localhost:8081/api/v1/health/live/
curl --fail http://localhost:8081/api/v1/health/ready/
```

Stop and remove the disposable test data:

```bash
docker compose --env-file .env.test.example --file compose.test.yml down --volumes --remove-orphans
```

The release gate is at least 85 percent backend domain and API coverage and at least 75 percent frontend logic coverage. Authorization, state transitions, transaction boundaries, and concurrency cases require direct tests regardless of the percentage.

## Application flow

Public visitors can browse the hospital directory and doctor availability. A patient registers, verifies an email address, books an available slot, and sees only their own appointments and queue ticket. A lost or expired verification message can be replaced from `/resend-verification` without revealing whether an account exists.

Reception confirms identity, creates walk ins when required, checks patients in, and records onsite payment status. Check in allocates the final privacy safe queue token. Doctors operate only their assigned queue. Administrators manage staff, directory settings, schedules, branding, and audit review.

The queue remains first in, first out by check in time. It does not perform medical triage. Defer, restore, no show, and override actions require a reason and produce an audit event.

After five valid completed visits, the estimated service duration combines 70 percent of the doctor’s recent median with 30 percent of the configured duration. It uses at most 20 recent valid visits and stays between 5 and 60 minutes. The patient sees a range, confidence label, last update time, and their token. They never see another patient’s name.

## Security model

The browser uses secure Django sessions and CSRF protection. Authentication tokens are not stored in browser local storage. Staff accounts are invitation only and require TOTP multifactor authentication. Patient self registration requires email verification.

Authenticated sessions expire after 30 minutes without activity and after eight hours in all cases. The production validator rejects values outside the approved safe bounds or an absolute timeout that is not longer than the idle timeout.

Every API starts from default deny permissions and filters records by the signed in user and active role. External write requests support idempotency keys. PostgreSQL constraints, transactions, and row locks protect booking, check in, queue advancement, and payment recording from duplicate requests.

Long running production containers run with restricted privileges, bounded resources, read only application filesystems, and private service networks. A short lived initialization process gives the non root Caddy account access to its certificate volumes, then exits. PostgreSQL has no published port. The cluster bootstrap account, migration owner, and runtime application account are separate. Django uses the runtime account without schema creation or database administration rights. Caddy applies the same origin policy, TLS, HSTS, a restrictive content security policy, and response hardening headers.

Health endpoints disclose no patient data, configuration, record counts, or secrets:

1. `/api/v1/health/live/` confirms that the API process can answer.
2. `/api/v1/health/ready/` confirms that required configuration and PostgreSQL are ready.

Report a security or privacy concern through a private security advisory. The full handling policy is in [.github/SECURITY.md](.github/SECURITY.md).

## Production images

The release workflow builds three images from one reviewed revision:

1. `mediqueue-api` runs Gunicorn and the notification worker.
2. `mediqueue-web` contains the immutable React build and Caddy policy.
3. `mediqueue-db` contains PostgreSQL 18 and checksum verified pgBackRest 2.59.0.

The database image uses the official pgBackRest 2.59.0 distribution asset and its published SHA256 checksum. GitHub's automatic tag archive is not used because it omits generated source files required by the Meson build.

The workflow scans each candidate for high and critical findings before publication. It publishes an SPDX software bill of materials and build provenance. Production configuration accepts only `@sha256:` image references.

There is deliberately no `latest` production tag.

## Staging and production deployment

Production assumes Ubuntu 24.04 LTS on a Bangladesh based server with at least 4 vCPU, 8 GiB memory, and 160 GiB NVMe storage. DNS, SMTP, monitoring, alert delivery, and approved encrypted backup storage are external prerequisites.

1. Copy `.env.staging.example` to `/etc/mediqueue/staging.env` or `.env.production.example` to `/etc/mediqueue/production.env` on the server.
2. Give the file root ownership and mode `640` with a dedicated deployment group that contains only the named `mediqueue-deploy` operator. Mode `600` is also accepted when commands run through a controlled root procedure.
3. Replace every placeholder. Use immutable image digests from the release evidence. Generate `MFA_ENCRYPTION_KEY` independently from the Django, database, SMTP, and backup secrets. It must contain at least 32 random characters and must remain stable while enrolled MFA devices exist. Rotating it requires a reviewed staff MFA recovery and reenrollment procedure.
4. Mount approved separate encrypted storage at `BACKUP_REPOSITORY_PATH`. The mount must not depend on the application database disk. Create its repository directory for the container PostgreSQL account before validation.

   ```bash
   sudo install -d -o 70 -g 70 -m 0750 /srv/mediqueue-backup
   ```
5. Keep `REAL_DATA_APPROVED=false` until every written launch gate passes. Keep `OFF_HOST_BACKUP_APPROVED=false` until a separate approved backup copy and a restore from that copy have been tested. The validator requires both approvals before a real data environment can pass.
6. Validate before making a change.

   ```bash
   bash scripts/validate-production.sh \
     --environment staging \
     --env-file /etc/mediqueue/staging.env
   ```

7. Deploy an approved release through the protected GitHub environment, or run the guarded script during the approved maintenance window.

   ```bash
   bash scripts/deploy.sh \
     --environment staging \
     --env-file /etc/mediqueue/staging.env \
     --release v0.1.0-rc.1 \
     --confirm DEPLOY:staging:v0.1.0-rc.1
   ```

The deployment stops on configuration failure, unexpected migration state, failed Django deployment checks, failed readiness, or failed public smoke checks. It creates and verifies a fresh recovery point before applying migrations.

### First configuration on a clean database

Complete this sequence once after the first staging deployment. Use the production environment only after the same sequence and its approvals have passed in staging.

1. Create the hospital configuration with the exact approved identity. Add the approved email, phone, and address arguments when available.

   ```bash
   docker compose --env-file /etc/mediqueue/staging.env --file compose.production.yml exec api \
     python manage.py bootstrap_hospital \
     --name "Approved Hospital Name" \
     --short-name "AHN"
   ```

2. Create the first named administrator. Enter the password only at the protected prompt and enroll the printed TOTP URI immediately.

   ```bash
   docker compose --env-file /etc/mediqueue/staging.env --file compose.production.yml exec api \
     python manage.py bootstrap_admin \
     --email named.admin@hospital.example \
     --display-name "Named Administrator"
   ```

3. Sign in with MFA. In the administrator workspace, create the first approved privacy notice and select `Publish and make this the active registration notice`. This uses `/api/v1/admin/privacy-notices/`. Do not paste the notice through a shell command because shell history is not approved evidence.

4. Confirm that the public hospital page shows the approved identity and exact active notice. Confirm that patient registration records consent to that notice version. Then configure departments, locations, chambers, named staff, doctors, and schedules through the protected administrator pages.

5. Run the doctor and receptionist UAT with synthetic patients. Verify booking, walk in, check in, queue call, defer, restore, completion, no show, onsite payment, notification failure, and audit review before changing `REAL_DATA_APPROVED`.

`seed_synthetic` is blocked when debug mode is false and is never part of staging or production provisioning.

The operational sequence, monitoring thresholds, incident severity, downtime procedure, and release record are defined in [production.md](production.md). A command example is not a substitute for that review.

## Backup, restore, and rollback

pgBackRest archives write ahead logs continuously. The supplied systemd timers request an incremental recovery point each hour and a full backup at 01:30 Asia/Dhaka. The repository is encrypted before storage and retained for 30 days.

After the repository is installed at `/srv/mediqueue` and the privileged `mediqueue-deploy` service account has approved Docker access, install and enable the reviewed timer units:

```bash
sudo install -m 0644 infra/systemd/mediqueue-backup-hourly.service /etc/systemd/system/
sudo install -m 0644 infra/systemd/mediqueue-backup-hourly.timer /etc/systemd/system/
sudo install -m 0644 infra/systemd/mediqueue-backup-daily.service /etc/systemd/system/
sudo install -m 0644 infra/systemd/mediqueue-backup-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mediqueue-backup-hourly.timer mediqueue-backup-daily.timer
sudo systemctl list-timers 'mediqueue-backup-*'
```

Membership that can control the Docker socket is equivalent to host administrator access. Limit it to the dedicated deployment service account, protect its credential, and audit every interactive use.

Run a manually approved recovery point:

```bash
bash scripts/backup.sh \
  --environment production \
  --env-file /etc/mediqueue/production.env \
  --type incr \
  --confirm BACKUP:production
```

`restore.sh` refuses to use the active project. It creates a new `mediqueue-restore-*` project, restores into a new database volume, and does not start the API, worker, or web service. Operators must complete integrity checks in that isolated environment before any application connection.

The repository also contains a destructive but isolated synthetic recovery exercise. It uses the fixed `mediqueue-recovery-test` project, confirms that exact name, creates an encrypted full backup, clears only that test database volume, restores it, checks a synthetic marker, and removes only its own resources.

```bash
bash scripts/recovery-test.sh --confirm RECOVERY-TEST:mediqueue-recovery-test
```

This exercise proves the container and repository mechanics on the current host. It does not replace the scheduled clean restore from approved off host storage or the measured RPO and RTO exercise.

Image rollback is allowed only after the operator confirms that the existing schema is compatible with the recorded previous image. Otherwise use the migration specific forward repair or the isolated restore procedure. No script deletes a failed database or backup during incident recovery.

## Go live boundary

Real patient data remains prohibited until all of these conditions have written evidence:

1. Final hospital identity, privacy notice, consent wording, retention schedule, access policy, support owner, and incident contacts are approved.
2. A qualified reviewer completes the current Bangladesh legal and data location review.
3. A doctor and receptionist sign the critical staging workflows.
4. Every staff account is named, correctly scoped, and protected by MFA.
5. The hospital record and active privacy notice match the approved text, and patient consent is traceable to that version.
6. The runtime database role is confirmed as non superuser, non owner, and unable to create schema objects.
7. No critical or high security finding and no Severity 1 or Severity 2 defect remains open.
8. Clean restore, rollback, alert delivery, notification failure, and downtime reconciliation exercises pass.
9. One trained department completes the controlled pilot before wider rollout.

See the complete evidence list in [production.md](production.md) and the scenarios in [test.md](test.md).

## Contribution and ownership

Work uses short lived branches and reviewed pull requests. The pull request must explain user behaviour, privacy and authorization effects, database changes, tests, and rollback. Use synthetic records in fixtures, screenshots, logs, and issue reports.

## Help assistant

Every authenticated workspace includes a role aware help assistant. It answers system usage questions and selected live operational questions without changing records. Private patient answers are produced inside Django. Groq receives only privacy safe questions and public or nonidentifying context when it is configured.

Create a Groq key at `https://console.groq.com/keys`, then place it in the ignored local `.env` file as `GROQ_API_KEY`. Never send the key through chat or commit it. Restart the API container after changing the environment. The assistant keeps working with local answers when the key is empty.

The complete behaviour, role boundary, API contract, safety rules, and production approval requirement are documented in `chatbot.md`.

This is a private project. No public open source licence is granted. Hospital ownership, university submission rights, contributor agreements, and third party asset rights must be confirmed before any distribution outside the approved team.
