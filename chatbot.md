# Hospital Help Assistant

## Purpose

The help assistant gives each signed in user one place to ask how the system works and to request current operational information. It is designed for hospital workflow questions. It is not a clinical assistant and it never performs diagnosis, treatment advice, emergency assessment, or medical triage.

The assistant has two answer paths. Controlled Django queries answer private and operational questions directly. Groq can improve the wording of safe general answers when a key is configured. The main workflows continue to work when Groq is not configured or temporarily unavailable.

## Supported users

### Patient

A patient can ask how to register, verify an email address, find a doctor, book, reschedule or cancel an appointment, check in, read a queue update, understand arrival guidance, review a payment state, use notifications, update a profile, or record a privacy choice.

Questions about the signed in patient’s appointment, token, queue position, location, and onsite payment record are answered inside Django. That information is never sent to Groq.

### Doctor

A doctor can ask about their working schedule, confirmed appointment pressure over the next seven days, today’s queue, patients waiting, queue controls, defer and restore rules, completion, no show handling, and the meaning of arrival estimates.

Doctor workload calculations use only the doctor linked to the signed in account. Patient names and patient identifiers are not included in pressure answers or sent to Groq.

### Receptionist

A receptionist can ask about today’s appointment, check in, waiting, and unpaid totals. The assistant also explains patient registration, duplicate review, permitted corrections, walk ins, appointment management, queue operation, and onsite payment recording.

The assistant reports aggregate totals. It does not provide a conversational patient search and it cannot change a record.

### Administrator

An administrator can ask about today’s hospital totals, low booked pressure over the next seven days, departments, locations, chambers, doctors, schedules, exceptions, staff invitations, notification failures, settings, privacy notices, and the audit trail.

Administrative answers are read only. Configuration changes still use the normal forms, permission checks, reasons, transactions, and audit events.

## Live information

Every request derives the role from the authenticated server session. The browser cannot select a more powerful role for the assistant.

The following information can be read when it is relevant to the question.

1. Public hospital identity and active doctor directory.
2. Current schedule rules, closures, replacement times, slot capacity, and confirmed bookings.
3. The signed in patient’s own upcoming appointments, queue token, queue state, location, number of waiting tokens ahead, and onsite payment state.
4. The signed in doctor’s own schedules, confirmed appointment counts, and assigned queue totals.
5. Hospital wide nonidentifying appointment, queue, and payment totals for reception and administration.
6. Active configuration totals and the next seven days of booked operational pressure for administrators.

Availability is calculated from the same scheduling service used by appointment booking. An answer is a snapshot. A slot is not reserved until the normal booking request succeeds.

## Privacy boundary

Groq receives only the user’s safe question, safe recent user questions, the user’s role, the approved system guide, public doctor availability when requested, and nonidentifying operational totals when needed. Locally generated assistant answers are not forwarded. Groq does not receive a patient name, MRN, email address, phone number, date of birth, address, queue token, payment reference, audit record, password, MFA code, session value, API key, diagnosis, symptom, or clinical note.

Questions containing common private identifiers or personal record phrases stay on the local answer path. The interface also tells users not to enter symptoms, credentials, or another person’s details. These controls reduce disclosure risk but do not replace the hospital’s privacy training and processor approval.

Conversation text is held in the current browser view only. This release does not create a chat transcript table and does not write question text to the audit trail or application log. The API records ordinary request metadata under the existing logging rules without the prompt body.

## Clinical safety

The assistant refuses diagnosis, treatment, prescription, dosage, symptom assessment, and triage requests. It directs an urgent concern to onsite clinical staff or local emergency services. It never changes queue priority for a medical reason.

The assistant cannot complete a booking, cancel an appointment, check in a patient, move a queue token, record a payment, invite staff, or change configuration. It can link the user to the correct authorized screen.

## Groq integration

The integration uses Groq’s OpenAI compatible chat completions endpoint at `https://api.groq.com/openai/v1/chat/completions`. The default model is the production model `llama-3.3-70b-versatile`. The model name is configurable because provider availability can change.

Configuration uses three environment values.

```text
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT_SECONDS=8
```

An empty key is valid and enables local answers only. The timeout is bounded from 2 to 20 seconds. A provider timeout, network failure, malformed response, or unavailable model returns a local answer instead of failing the hospital workflow.

To create a key, sign in at `https://console.groq.com/keys`, create a project key, and copy it once into the ignored local `.env` file. Do not paste the key into source code, a document, an issue, a screenshot, GitHub, or chat. Restart the API container after changing the environment.

For local development:

```text
docker compose --env-file .env up --build --detach
```

For staging or production, an operator stores the key in the protected environment file outside Git. Real data use remains disabled until the hospital and privacy reviewer approve Groq as an external processor and record the applicable agreement, data location, retention, access, incident, and deletion terms.

## API contract

`POST /api/v1/assistant/chat/` requires an authenticated session. Staff sessions must have completed MFA.

The request contains a message of 2 to 600 characters and up to six recent conversation turns. Each prior turn is limited to 800 characters. Unknown fields are rejected.

The response contains the answer, effective role, answer provider, live data flag, freshness time, source labels, safe application links, and suggested follow up questions.

The endpoint is limited to 20 requests per user per minute. It applies the same CSRF, secure session, request size, error format, proxy, and security header controls as the rest of the API.

## Failure behaviour

1. If Groq is not configured, the assistant answers from local workflow guidance and controlled database queries.
2. If Groq times out or returns an invalid response, the same request receives a local answer.
3. If the database has no active hospital, the assistant reports that configuration must be completed.
4. If a doctor account has no active doctor profile or schedule, the answer states that clearly.
5. If a patient has no active appointment or queue token, the assistant explains the next valid action.
6. If an answer contains live information, the interface marks it as live and exposes its freshness time.

## Verification

Backend tests cover authentication, staff MFA, strict input validation, role scoping, private patient appointments, patient payment, queue token access, live availability, doctor workload, staff aggregate totals, clinical refusal, provider failure, provider success, identifier filtering, workflow guidance, and conversation limits.

Frontend tests cover opening and closing the assistant, role specific prompts, sending a question, displaying a live answer, source labels, and safe route links. The browser flow verifies a real patient availability question through the assembled application.

Before real data launch, the hospital must also complete privacy review, prompt abuse testing, rate limit testing, provider outage testing, accessibility review, and role based UAT.
