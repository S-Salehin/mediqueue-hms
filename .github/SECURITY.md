# Security reporting

This repository is intended to remain private. Report a suspected vulnerability through a private GitHub security advisory or directly to the named technical owner in the hospital access register.

Do not open a normal issue for an access control defect, exposed credential, personal data disclosure, or active compromise. Do not include real patient information in a report. Use synthetic identifiers and redact cookies, session values, email bodies, request bodies, and secrets.

Include the affected release, route or workflow, the minimum safe reproduction steps, observed impact, and a secure way to contact you. The team will acknowledge a credible critical report within 15 minutes during the supported pilot period and follow the incident procedure in `production.md`.

Only the current production candidate receives security fixes during the pilot. Older demonstration revisions are not supported. A deployment is not approved for real patient data until every launch gate in `production.md` has written evidence.
