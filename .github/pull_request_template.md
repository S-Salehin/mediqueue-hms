## Purpose

Describe the problem and the result in plain language.

## Behaviour

Explain what changed for patients, doctors, receptionists, administrators, or operators.

## Risk and privacy

State the authorization, personal data, audit, concurrency, notification, and security effects. Write `None` only after checking each area.

## Database and deployment

List migrations, compatibility limits, configuration changes, and the tested rollback or restore decision.

## Verification

List automated checks and manual scenarios completed. Use synthetic data and attach privacy safe evidence.

## Release checklist

- [ ] The change is within the approved pilot boundary.
- [ ] Access is default deny and object permissions are tested where applicable.
- [ ] New write operations are safe under retry and concurrency where applicable.
- [ ] Logs, screenshots, fixtures, and errors contain no real patient data or secrets.
- [ ] Migrations apply to an empty PostgreSQL 18 database.
- [ ] Accessibility and keyboard behaviour were checked for interface changes.
- [ ] Documentation and regression tests were updated.
- [ ] The rollback or restore path is recorded.
