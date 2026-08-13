# Source and Production Audit

## 1. Audit record

Audit baseline: 14 August 2026  
Project: Hospital Operations and Adaptive Queue Production Pilot  
Development name: MediQueue  
Audit scope: three supplied PDF documents and four supplied interface images

This audit records what the supplied material actually says, where it conflicts, and what must change before the system can handle real hospital data. It is a requirements and design audit. It is not evidence that the application, infrastructure, security controls, or hospital procedures already exist.

Page references use the physical PDF page number shown by a PDF reader. This avoids ambiguity in the progress report because physical page 11 repeats the printed footer number 10. The image references use the exact supplied file names.

The source PDFs include student identifiers, staff names, signatures, and dates. The source images include realistic patient and doctor identities. Those files are excluded from Git by exact path. This audit does not repeat student identifiers or reproduce signatures.

## 2. Project context and controlling intent

The documents share one clear purpose. The system should replace fragmented manual administration for doctor records, patient registration, appointment booking, and operational monitoring. The later interface references add live queue visibility so a patient has better information about when to arrive.

The production interpretation is:

1. Help one small hospital manage appointments and outpatient queues safely.
2. Reduce repeated data entry, booking conflicts, and uncertainty about waiting.
3. Give each role only the information and actions needed for its work.
4. Keep the first release operational rather than clinical.
5. Never present a wait estimate as medical advice or use it to prioritise care.

The phrase “Skip the Waiting Room” appears in every supplied interface image. It is not an acceptable operational promise. A queue system can reduce unnecessary waiting and provide arrival guidance, but it cannot guarantee that a patient will not wait. Production wording must state that estimates can change and that urgent medical concerns must use the hospital’s approved emergency route.

## 3. Source inventory and page review

### 3.1 Title Phase Evaluation Report

Source: `HMS Title_Phase_Evaluation_Report (1064 & 1051).pdf`

| PDF page | Evidence and audit finding |
| --- | --- |
| 1 | Identifies the Fall 2025 title phase, project members, academic supervisors, submission date, and signed certification. It approves the project title. It does not approve production use, a hospital deployment, or a final technical design. |
| 2 | Defines the problem as manual or partly digitised hospital work involving doctor schedules, patient registration, appointments, records, payment, and dashboards. It proposes React, Django, and MySQL. No hospital, respondent, measured baseline, or workflow evidence is identified. |
| 3 | Describes paper records, delayed retrieval, appointment errors, Practo, ERP products, React, Django, MySQL, and SQLite. It calls for separate admin, doctor, and patient access. Claims about cost, complexity, training, and demand are not tied to evidence. |
| 4 | States the problem, generic novelty, one research question, and objectives. Objectives include online payment, secure admin login, role based access, and a real time dashboard. The novelty claim is a combination of common technologies and does not establish a research contribution. |
| 5 | Expects online payment, record management, role interfaces, and dashboard totals. It allows Tailwind or Bootstrap and MySQL or SQLite. It excludes EMR, AI diagnosis, cloud scalability, and multi hospital support. It explicitly says the system is for educational and small scale use, not full commercial deployment. All five academic references on this page are unusable as written. |
| 6 | Contains an empty supervisor feedback area and an examiner signature. No written examiner correction, acceptance condition, or production requirement is supplied. |

### 3.2 Proposal Approval Form

Source: `Proposal Approval Form (1).pdf`

| PDF page | Evidence and audit finding |
| --- | --- |
| 1 | Identifies the students, semester, proposed title, supervisor, approval date, and signature. The approval is academic. It contains no production risk acceptance. |
| 2 | Limits the stated operational objective to doctors, patients, appointments, counts, records, and administrator or staff use. It proposes React and Django and claims scalability without defining load, availability, or data volume. |
| 3 | Lists a central dashboard, responsive access, React, HTML, CSS, Bootstrap or Tailwind, Django, and MySQL or SQLite. The only detailed modules are a public landing area and an administrator panel. Doctor, patient, receptionist, payment, queue, notification, consent, and audit workflows are not specified. Status examples are only active, inactive, and scheduled. |
| 4 | Promises a functional responsive system and real time monitoring. It first discusses small and medium hospitals, then concludes that the solution is scalable for hospitals of all sizes. No architecture or evidence supports the wider claim. |

### 3.3 Phase I Evaluation Report

Source: `Defense_Phase 1 (0242220005101064).pdf`

| PDF page | Evidence and audit finding |
| --- | --- |
| 1 | Identifies the Spring 2026 Phase I report, the project team, the software engineering theme, submission details, and supervisor certification. It contains personal identifiers and a signature and must not enter the repository. |
| 2 | Changes the stack to Python, Django, HTML, CSS, Bootstrap, and SQLite. It describes patient registration, doctor management, appointments, and record keeping, but not React, an API, queue operation, or production controls. |
| 3 | Repeats the small hospital gap and core objectives. Four embedded public site screenshots show Home, Medical Services, Contact, and About pages. They demonstrate appearance only and do not prove permissions, data integrity, or hospital validation. |
| 4 | Shows an administrator login, dashboard, and create or list screens for doctors, patients, and appointments. The screens use a separate earlier design and do not show patient, doctor, receptionist, queue, payment, consent, notification, or audit behavior. |
| 5 | Supplies an ER diagram with `ADMIN`, `DEPARTMENT`, `DOCTOR`, `PATIENT`, `APPOINTMENT`, `CONTACT_MESSAGE`, and `ABOUT_INFO`. It contains invalid or unexplained relationships and lacks the entities and constraints required for the approved production scope. Section 7 records the detailed defects. |
| 6 | Says needs were gathered through observation, informal discussions, online sources, research articles, existing systems, feedback, and qualitative analysis. It gives no hospital name, dates, sample size, participant roles, questions, observations, consent, raw findings, or requirements approval. The claims cannot be independently reproduced. |
| 7 | Claims that planning, literature review, architecture, diagrams, user interface pages, Django setup, routing, an initial schema, and admin authentication were completed. It also claims working navigation and credential validation. No source code, Git history, schema, tests, or deployment material was supplied to this workspace, so those implementation claims cannot be accepted as the starting code baseline. |
| 8 | Records development challenges and plans dashboard, patient management, doctor scheduling, and payment work for May and June 2026. Payment is left undecided between a gateway and manual tracking. The timeline begins but has no named owner, deliverable evidence, acceptance test, or dependency. |
| 9 | Continues the timeline and names Django, HTML, CSS, Bootstrap, SQLite or MySQL, GitHub “if used,” tutorials, and sample systems. The wording confirms that version control evidence was uncertain. It describes a phased and agile style but no actual backlog or review record. |
| 10 | Estimates software at zero BDT and optional hosting at zero to 1,000 BDT. That estimate covers an academic demonstration, not a production host, encrypted offsite backups, a domain, transactional email, monitoring, maintenance, incident response, or security review. Security and scalability appear only as future concerns. |
| 11 | Lists official product documentation, then describes what an appendix could include. It does not supply the claimed source code snippets, database schema detail, workflow evidence, or test results. |
| 12 | Contains the university template instructions. The instruction requiring error free English is not a system requirement. It does show that the report is an academic progress template rather than a production acceptance record. |
| 13 | States document access and copyright conditions. It does not grant permission to publish student identifiers, signatures, or the supplied scans in a Git repository. |

## 4. Requirement traceability and production interpretation

| Requirement | Source evidence | Production decision | State |
| --- | --- | --- | --- |
| Public information pages | Defense pp. 3 to 4, Proposal p. 3 | Keep a small public directory, hospital contact, privacy notice, and sign in entry. Hospital supplied content is required before launch. | Accepted |
| Patient registration | Title pp. 2 to 5, Proposal pp. 2 to 3, Defense pp. 2 to 3 | Support verified patient self registration and receptionist created unclaimed profiles. Generate a unique MRN. | Accepted |
| Patient records | Title pp. 2 to 5, Proposal pp. 2 to 4, Defense pp. 2 to 3 | Limit v1 to identity, contact, consent, appointment, queue, notification, and payment records. Do not store clinical notes, diagnoses, prescriptions, or results. | Narrowed |
| Doctor management | All three documents | Support department, location, public profile, account, schedule, closure, and active state. Do not use unsupported ratings or verification badges. | Expanded safely |
| Appointment scheduling | All three documents | Support availability, capacity, booking, rescheduling, cancellation, check in, walk ins, no show, and immutable state history. | Expanded safely |
| Appointment payment | Title pp. 2, 4, 5; Proposal p. 3; Defense p. 8 | Record onsite payment in BDT. Do not process or store card details and do not integrate an online gateway in v1. | Narrowed |
| Administrator access | Title pp. 3 to 5, Proposal p. 3, Defense pp. 4 and 7 | Use one user model and explicit role assignments. Administrators manage configuration and audit access. They do not silently rewrite business history. | Replaced design |
| Doctor access | Title pp. 3 and 5, supplied doctor image | Doctors see their own schedules and assigned queue only, with minimum patient identity. | Accepted with restriction |
| Reception work | Proposal p. 2 refers to staff but gives no role; not shown elsewhere | Add a named receptionist role for registration, booking, check in, walk ins, queue operation, and onsite payment. | Required production addition |
| Role based access | Title pp. 3 to 5 | Default deny, queryset filtering, object checks, staff invitation, staff MFA, and access audit are required. Separate unaudited login systems are rejected. | Replaced design |
| Real time dashboard | Title pp. 2, 4, 5; Proposal pp. 3 to 4; supplied queue images | Use privacy safe conditional polling. “Real time” means a connected queue view no more than 15 seconds behind committed state under the approved load. | Defined |
| Queue tokens | Supplied booking, patient, and doctor images | Allocate the final token at check in, not at booking. Tokens are unique within a queue session and reveal no other patient identity. | Replaced design |
| Wait estimate | Supplied booking, patient, and doctor images | Display a range, confidence label, last updated time, and stale state. Use historical service duration only. Do not infer medical urgency. | Replaced design |
| Notifications | Supplied booking and patient images | Provide in app and privacy safe email notifications through a transactional outbox. Email failure must not roll back a valid business event. | Accepted with controls |
| Dashboard totals | Title pp. 4 to 5, Proposal p. 3, Defense pp. 4 and 7 | Show role appropriate operational counts. Do not expose patient lists or sensitive aggregates to public users. | Accepted with restriction |
| Contact messages | Defense p. 5 ER diagram | A public contact form is not required for the six day pilot. Publish an approved hospital contact route instead. | Deferred |
| About content | Defense pp. 3 and 5 | Store approved hospital identity as configuration if needed. A general purpose content management system is not required. | Simplified |
| Security | Title p. 4, Defense pp. 3 and 10 | Treat security as release work. Apply OWASP ASVS 5.0 Level 2 controls where applicable and verify them. No blanket “secure” claim is permitted. | Required gate |
| Accessibility | “User friendly” throughout, but no standard is named | Target WCAG 2.2 AA for complete critical workflows and test with keyboard and screen reader use. | Required production addition |
| Production deployment | Title p. 5 explicitly excludes commercial deployment; user brief requires production | Build a production candidate, use synthetic data first, and permit real data only after all launch gates are signed. | Controlled scope change |
| Multi hospital support | Title p. 5 | One hospital only. Do not add tenancy abstractions to v1. | Excluded |
| EMR and diagnosis | Title p. 5 | Exclude clinical documentation, medical advice, diagnosis, triage, laboratory, pharmacy, inpatient, and prescription functions. | Excluded |

## 5. Contradictions and missing evidence

| Finding | Conflicting evidence | Accepted resolution |
| --- | --- | --- |
| Educational system versus live hospital system | Title p. 5 says educational and small scale, not commercial. The delivery brief requires a deployed hospital system. | The six day result is a production candidate and controlled pilot. Real patient data remains prohibited until legal, hospital, security, infrastructure, restore, and UAT gates pass. |
| Frontend stack | Title p. 2 and Proposal pp. 2 to 4 specify React. Defense p. 2 and the older screens use server rendered HTML, CSS, and Bootstrap. | React 19 with JavaScript, Vite, Tailwind CSS, and an accessible custom component layer. |
| Database | Title and Proposal alternate between MySQL and SQLite. Defense alternates between SQLite and MySQL. | PostgreSQL 18 in local, CI, staging, and production because booking and queue correctness depend on transactions, row locks, and constraints. |
| Interface library | Title and Proposal leave Tailwind or Bootstrap undecided. Defense uses Bootstrap. | Tailwind CSS plus project owned accessible components. Do not combine two component systems. |
| Payment | Title requires online payment. Defense p. 8 leaves gateway or manual tracking open. | Onsite payment recording only. No card details, gateway, settlement, or online refund processing. |
| Patient records versus EMR exclusion | The documents repeatedly promise patient records, while Title p. 5 excludes EMR. The booking image asks for symptoms. | Store administrative patient and visit records only. Remove the symptom field and do not create a clinical note model. |
| Role set | Title describes admin, doctor, and patient. Proposal mentions staff without defining it. The supplied screens omit reception. | Patient, doctor, receptionist, and hospital administrator roles. Staff access is invitation only and requires MFA. |
| Real time behavior | The documents and images use “real time” without a transport, freshness limit, or failure state. | Conditional polling every 10 seconds while active and 30 seconds in the background. Mark the view stale after 30 seconds without success. |
| Scalability | Proposal p. 4 says hospitals of all sizes. Title p. 5 says educational and small scale. No measurement is supplied. | Pilot limit of 30 doctors, 500 appointments per day, and 50 concurrent users. Wider claims require new testing and architecture review. |
| Novelty | Title p. 4 claims novelty from React, Django, simplicity, and scalability. These are common implementation choices. | The research contribution is the documented combination of adaptive arrival ranges and a fairness audit. It is not described as a worldwide first. |
| Progress baseline | Defense p. 7 claims working Django code, authentication, pages, and a schema. No code, history, schema, or tests were transferred. Defense p. 9 says GitHub “if used.” | Begin from scratch. The old screenshots are references only. Future reports must link each completion claim to a revision and test evidence. |
| Cost | Defense p. 10 estimates nearly free work and optional low cost hosting. | Use the production cost model in `production.md`. Infrastructure, email, backups, monitoring, operations, legal review, and maintenance are real costs. |
| Needs assessment | Defense p. 6 claims observation and informal discussion but supplies no reproducible evidence. | Doctor, receptionist, administrator, and privacy or legal representatives must review and sign the critical workflows before real data launch. |

## 6. Citation integrity review

The five academic references on Title report page 5 must not be copied into the final report. Three conflict with the stated publication record. Two could not be verified as written. None supplies a DOI or stable article link.

| Reference as supplied | Verification | Result |
| --- | --- | --- |
| Kumar and Goyal, “A study of Hospital Management System,” IJCA 179(23), 2018, pp. 1 to 5 | The [official IJCA issue contents](https://www.ijcaonline.org/archives/volume179/number23/) list the articles and authors for volume 179 number 23. This title and these authors are absent. | Contradicted by the stated issue |
| Kelkar and Gupta, “Review of digital healthcare management systems,” IJARCS 10(5), 2019, pp. 12 to 17 | The [official IJARCS issue contents](https://www.ijarcs.info/index.php/Ijarcs/issue/view/85) list every article and page range. Pages 8 to 12 and 13 to 16 belong to unrelated articles, and the supplied title and authors are absent. | Contradicted by the stated issue |
| Sharma and Gupta, “Web based hospital information systems using modern technologies,” ICCCA 2020, pp. 554 to 560 | The [ICCCA 2020 proceedings contents](https://www.proceedings.com/content/056/056578webtoc.pdf) place “Fast Trilateral Filtering for Video Denoising” at page 554 and the next unrelated paper at page 559. No hospital paper with the supplied title appears. | Contradicted by the proceedings |
| Patel, “Analysis of appointment scheduling systems in healthcare,” IEEE Access 8, 2020, pp. 112450 to 112460 | Exact title, author, journal, year, and page searches returned no publisher or DOI record matching the citation. | Unverifiable as written |
| Singh, Chauhan, and Verma, “Design and implementation of a hospital management information system,” IEEE conference, 2021, pp. 233 to 238 | The conference name is incomplete and no exact title and author match, DOI, catalog number, location, or stable proceedings record was found. | Unverifiable as written |

Verification was performed on 14 August 2026. An unverifiable reference is not proof that no similarly named work exists. It means the supplied citation cannot support an academic claim and must be replaced rather than guessed.

Recommended genuine sources are:

1. Ali Ala and Feng Chen, [“Appointment Scheduling Problem in Complexity Systems of the Healthcare Services: A Comprehensive Review”](https://doi.org/10.1155/2022/5819813), Journal of Healthcare Engineering, 2022.
2. Nadine Ostern, Guido Perscheid, Jürgen Riedel, and Jörg Moormann, [“Keeping pace with the healthcare transformation: a literature review and research agenda for a new decade of health information systems research”](https://doi.org/10.1007/s12525-021-00484-1), Electronic Markets, 2021.
3. World Health Organization, [Guidance for health information system governance](https://www.who.int/europe/publications/i/item/WHO-EURO-2021-1999-41754-57182), 2021.
4. OWASP Foundation, [Application Security Verification Standard 5.0.0](https://owasp.org/www-project-application-security-verification-standard/), for application security requirements and verification.
5. World Wide Web Consortium, [Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/), for accessibility acceptance.
6. Bangladesh Government Press, [April 2026 extraordinary gazette index](https://www.dpp.gov.bd/bgpress/bangla/index.php/document/extraordinary_gazettes_monthly/2026-04-14), which records the Personal Data Protection Act 2026, National Data Management Act 2026, and Cyber Security Act 2026. A qualified Bangladesh reviewer must interpret the applicable duties before live use.
7. Directorate General of Health Services, [Bangladesh Core FHIR Implementation Guide](https://fhir.dghs.gov.bd/core/), as a future interoperability reference only. This release does not claim FHIR conformance.

## 7. ER diagram audit

The ER diagram on Defense page 5 is not a usable production schema.

| Defect | Evidence in the diagram | Required correction |
| --- | --- | --- |
| Unsafe authentication model | `ADMIN` contains `username` and `password` as general `VARCHAR` fields. Patient and doctor accounts do not exist. | Use the Django custom user model, password hashing, one identity boundary, role assignments, staff invitations, MFA devices, sessions, login audit, and recovery controls. Never design a plain password column. |
| Foreign keys are not identified | A legend defines an FK marker, but `department_id`, `patient_id`, and `doctor_id` are not marked as foreign keys. | Declare actual foreign keys, deletion behavior, indexes, uniqueness, and database constraints in migrations. |
| Invalid appointment relationship | `APPOINTMENT` “manages” `CONTACT_MESSAGE` in a one to many relationship. There is no business meaning for an appointment managing public messages. | Remove the relationship. A contact feature, if later approved, must have its own purpose, owner, retention, spam control, and access policy. |
| Unnamed invalid lines | Lines connect `ADMIN` to `CONTACT_MESSAGE` and `CONTACT_MESSAGE` to `ABOUT_INFO` without a named relationship or matching foreign key. | Remove them. Model explicit auditable ownership only where a real workflow requires it. |
| Ambiguous cardinality | The patient booking edge prints repeated `N` labels and no relationship shows whether participation is optional. | Express cardinality through foreign keys, null rules, unique constraints, and tested domain invariants rather than an ambiguous picture. |
| No hospital structure | There is no hospital, chamber or location, service timezone, or configuration entity. | Add hospital, department, and location records with one configured hospital boundary. |
| No schedule or capacity | A single appointment datetime cannot represent recurring schedules, closures, duration, capacity, or availability. | Add schedule and schedule exception records and calculate availability from them. Enforce capacity transactionally. |
| No appointment history | `status` is an unrestricted string and only current state is retained. There is no reschedule, cancellation reason, actor, or idempotency record. | Use constrained states, immutable state history, request idempotency, timestamps, and actor attribution. |
| No queue | There is no queue session, token, ticket, event, check in time, service start, completion, defer, no show, or ordering field. | Add queue sessions, tickets, event history, transactional token allocation, and one active service constraint. |
| Clinical scope leak | `APPOINTMENT.reason` can become an ungoverned symptom or clinical note. The booking image also asks for symptoms. | Remove free form clinical content from v1. Keep only administrative notes with a documented purpose if hospital review proves they are necessary. |
| Weak patient identity | There is no MRN, account claim state, email verification, active state, duplicate review, correction history, or consent. | Add generated MRN, claim and verification state, duplicate warning workflow, correction audit, privacy notice version, and consent record. |
| No payment model | Payment is an objective but absent from the diagram. | Add an onsite payment record with integer BDT minor units, constrained state, actor, idempotency, correction history, and no card fields. |
| No notification reliability | Email is stored but there is no preference, notification, outbox, retry, or delivery history. | Add notification, preference, outbox, attempt, and terminal failure records. Keep queue emails minimal. |
| No audit model | Administrative changes and access are not traceable. | Add append only business audit events and security login audit. Limit access and prevent edit or delete through the application. |
| Inappropriate identifier exposure | Every entity uses a sequential integer identifier with no external identifier policy. | Use UUID external identifiers and keep database internals private. Do not rely on unpredictable identifiers for authorization. |
| Missing validation | Phone, email, status, gender, timestamps, and money have no format, length, check, uniqueness, or timezone rules. | Use E.164 phone numbers, normalized email, UTC storage, Asia/Dhaka display, constrained choices, integer money, and explicit validation. |

## 8. Supplied interface audit

### 8.1 Screen by screen findings

| Image | Observed intent | Defects and production decision |
| --- | --- | --- |
| `WhatsApp Image 2026-08-10 at 2.13.04 AM.jpeg` | Patient and doctor login tabs, registration, password recovery, persistent sign in, live serial messaging, and support messaging | No receptionist or administrator route is shown. Staff MFA and invitation state are absent. “Remember me” appears selected, which is unsafe as a default on shared reception or family devices. “Your data is safe with us” is an unsupported assurance. Replace tabs with clear role appropriate entry, default persistent sign in to off, and show only verified security and support wording. |
| `WhatsApp Image 2026-08-10 at 2.13.04 AM (1).jpeg` | Patient books a named doctor for 17 June 2025 at 10:30 AM, sees fee, shift, patient note, booking count, serial, and wait estimate | A final serial is shown before check in. The symptom prompt introduces clinical data outside scope. Shift and slot inputs overlap. The rating, review count, verified badge, experience, institution, fee, phone number, and instant confirmation claim have no source or data ownership. Allocate the token at check in, remove symptoms and unsupported claims, derive one availability choice from the schedule, and confirm only after the transactional write succeeds. |
| `WhatsApp Image 2026-08-10 at 2.13.04 AM (2).jpeg` | Patient dashboard shows live queue, current service, a wait estimate, notifications, and the patient’s appointment history | It exposes the full name of the patient currently being served to another patient. This is a direct privacy defect. It also uses a single approximate wait with no range, confidence, last updated time, or stale state. Show only the current token, never another patient’s name, and add range, confidence, freshness, and reconnecting behavior. |
| `WhatsApp Image 2026-08-10 at 2.13.04 AM (3).jpeg` | Doctor dashboard shows counts, current patient, today’s queue, completion, and skip or next controls | Patient names, age, and gender require an assigned care relationship and data minimisation review. “Skip / Next” has no defined state, reason, confirmation, restore route, or audit trail. “Mark as Completed” also lacks service start and concurrency behavior. Limit the list to the doctor’s assigned queue and implement call, start, defer, restore, complete, and no show as explicit audited transitions. |

### 8.2 Cross screen data conflict

The four images cannot be treated as one coherent test dataset.

1. The booking screen assigns Arif Hossain serial 12 with Dr. Mahmudul Hasan on 17 June 2025 at 10:30 AM.
2. The patient dashboard assigns Arif Hossain serial 15 for the same doctor, date, and time.
3. The doctor dashboard assigns serial 12 to Hasan Mahmud at 11:30 AM.
4. The doctor dashboard assigns serial 15 to Nusrat Jahan at 1:00 PM.
5. The patient dashboard displays Rahim Uddin as the current patient, proving that another patient identity is sent to the patient view.

Serials 12 and 15 therefore identify two different people each within the apparent same doctor and date context. Production fixtures must be generated from one relational dataset. A queue token is unique within its queue session, and patient responses must be filtered before serialization.

### 8.3 Accessibility and interaction gaps

Static images cannot prove semantics, focus behavior, keyboard operation, accessible names, status announcements, error association, reflow, reduced motion, or screen reader output. The light borders and pale status colors also require measured contrast testing. Visual similarity to these references is not acceptance. Complete patient, doctor, receptionist, and administrator workflows must meet the `test.md` accessibility scenarios.

## 9. Data classification

| Class | Examples in this system | Minimum handling rule |
| --- | --- | --- |
| Public | Approved hospital identity, department, chamber, doctor public profile, public availability, support route, privacy notice | Hospital approved content only. Prevent unauthorised editing. Do not publish staff private contact details. |
| Internal | Aggregate daily counts, capacity settings, nonidentifying queue performance, deployment metadata, ordinary operational procedures | Authenticated staff with a work need. Do not include patient identifiers in metrics or health endpoints. |
| Confidential personal | Name, date of birth, gender when justified, phone, email, address, MRN, appointment doctor and time, status, notification destination, consent | TLS in transit, controlled storage, least privilege, object filtering, access logging, approved retention, correction process, and no public cache. |
| Restricted operational and financial | Token to patient mapping, assigned queue list, check in and service timestamps, onsite payment amount and state, account claim evidence, detailed audit events | Named authorised roles only. Never expose another patient’s mapping. Preserve history and record every correction. No card data. |
| Restricted security | Password hashes, MFA seeds, recovery tokens, sessions, secret keys, database credentials, backup encryption material, detailed login evidence | Never return through business APIs or write to ordinary logs. Encrypt and separate secrets, rotate them, restrict operator access, and redact support evidence. |
| Excluded clinical | Symptoms, diagnosis, prescription, clinical notes, test results, triage score, medical attachments | Do not collect or store in v1. If entered into an unintended free text field, treat it as restricted data and follow the correction and incident procedure. |

The final legal classification, lawful basis, consent wording, retention periods, data subject request process, hosting location, vendor terms, and incident notification duties require a qualified Bangladesh legal and privacy review. This table is an engineering control baseline, not legal advice.

## 10. Permission matrix

Legend: `R` read, `C` create, `U` controlled update, `A` approved action, `M` manage, blank means denied.

| Resource or action | Public | Patient | Doctor | Receptionist | Administrator |
| --- | --- | --- | --- | --- | --- |
| Approved hospital and doctor directory | R | R | R | R | M |
| Own user profile and session |  | R U | R U | R U | R U |
| Patient self registration and email verification | C | A |  |  |  |
| Staff invitation, role, and active state |  |  |  |  | M |
| Own patient profile and consent |  | R U |  |  | R U |
| Patient search and duplicate warning |  |  |  | R C A | R C A |
| Own appointments and payment records |  | R C A |  |  | R |
| Patient appointments and onsite payments |  |  | Assigned R | R C U A | R C U A |
| Doctor’s own schedule and exceptions |  |  | R | R | M |
| Department, location, and all schedules | Public subset R | Public subset R | Assigned R | R | M |
| Assigned queue and minimum patient identity |  | Own ticket R | R A | R A | R A |
| Queue call, start, defer, restore, complete, no show |  |  | Assigned A | A | A |
| Own notifications and preferences |  | R U | R U | R U | R U |
| Failed notification operations |  |  |  |  | R A |
| Aggregate operational dashboard |  | Own R | Assigned R | R | R |
| Business audit search |  |  |  |  | R |
| Edit or delete an audit event |  |  |  |  |  |
| Direct production database change |  |  |  |  |  |

Administrator access is not a bypass around purpose limitation. An administrator can investigate and configure the service but cannot impersonate a patient, silently edit immutable history, view security secrets, or use direct database writes as normal work.

## 11. Threat and risk register

The rating is the risk before implementation evidence. Every control below is required and remains unproven until its named tests pass.

| Risk | Threat and consequence | Initial rating | Required control | Release state |
| --- | --- | --- | --- | --- |
| R01 | A changed UUID returns another patient’s appointment, queue, payment, or profile through broken object authorization. | Critical | Default deny permissions, filtered querysets, object checks, response minimisation, and cross account API tests. | Open, blocks real data |
| R02 | A stolen or shared staff account exposes patient data or changes queue state. | Critical | Invitation only staff access, TOTP MFA, secure sessions, lockout, access review, named accounts, login audit, and immediate deactivation. | Open, blocks real data |
| R03 | Two requests consume the last capacity or create duplicate bookings. | Critical | PostgreSQL transaction, row lock, capacity constraint, idempotency key, unique invariant, and contention test. | Open, blocks release |
| R04 | Concurrent call or completion actions put two patients in service or corrupt FIFO order. | Critical | Locked queue session, legal state machine, one active service constraint, idempotency, event history, and simultaneous action test. | Open, blocks release |
| R05 | Patient queue output includes another patient’s name, as shown in the reference image. | Critical | Separate role serializers, token only patient snapshot, automated privacy assertion, and browser verification. | Open, blocks release |
| R06 | Symptoms or appointment details leak through email, logs, errors, monitoring, analytics, or support evidence. | High | Do not collect symptoms, use minimal email and logs, structured redaction, generic errors, no third party analytics with personal data, and log inspection tests. | Open, blocks real data |
| R07 | CSRF, XSS, injection, or unsafe uploads change or disclose records. | High | Same origin secure session design, CSRF enforcement, output escaping, input validation, parameterised ORM use, security headers, no uploads in v1, and ASVS verification. | Open, blocks real data |
| R08 | A secret or source document is committed to Git or exposed in a container or client bundle. | Critical | Exact ignore rules, environment secret storage, secret scanning, image scan, frontend build inspection, rotation procedure, and repository access control. | Open, blocks real data |
| R09 | An unencrypted, untested, or publicly reachable backup causes data loss or disclosure. | Critical | Encrypted offsite recovery material, separate credentials, no public database port, one hour RPO, four hour RTO, clean restore exercise, and access review. | Open, blocks real data |
| R10 | An incorrect wait estimate causes missed turns, excessive waiting, or false confidence. | High | Range rather than point promise, confidence and freshness label, conservative fallback, no clinical priority, accuracy monitoring, and staff override with reason. | Open, pilot monitored |
| R11 | A staff member defers, restores, completes, or marks no show without accountability. | High | Explicit state transitions, reason for defer and override, actor and timestamp, immutable event, least privilege, and daily exception review. | Open, blocks release |
| R12 | Duplicate or wrongly claimed patient identity attaches appointments to the wrong person. | Critical | Generated MRN, duplicate warning, no automatic merge, identity confirmation, controlled claiming, correction audit, and UAT. | Open, blocks real data |
| R13 | Notification retries send duplicates or email failure blocks a valid booking. | High | Transactional outbox, idempotent worker, attempt history, retry limit, terminal failure visibility, and mail outage test. | Open, blocks release |
| R14 | Dependency, container, or host compromise exposes the service. | High | Exact locks, dependency and image scans, supported versions, minimum container privileges, patch routine, firewall, TLS, monitoring, and incident response. | Open, blocks real data |
| R15 | A service outage stops reception and loses actions performed during downtime. | High | Health checks, alerts, approved numbered paper log, reconciliation, backups, restore, rollback, and trained incident contacts. | Open, blocks real data |
| R16 | The hospital launches without valid privacy, retention, consent, vendor, or incident decisions. | Critical | Qualified legal review, hospital approvals, processing inventory, signed launch record, and no production data before approval. | Open, blocks real data |
| R17 | Excessive administrator access or direct database edits bypass the audit trail. | High | Purpose limited admin UI, append only audit events, no ordinary database access, emergency change procedure, and periodic access review. | Open, blocks real data |
| R18 | Sequential scraping or automated requests enumerate doctors, accounts, or availability and degrade service. | Medium | UUID external identifiers, generic account responses, rate limits, pagination, request monitoring, and load tests. | Open, pilot monitored |

Detailed defect ownership and status belong in `bugs.md`. Security incidents follow `production.md` even when the triggering defect began as a normal bug.

## 12. Accepted design decisions

1. One small hospital, up to 30 doctors, 500 appointments per day, and 50 concurrent users.
2. React 19 with JavaScript, Vite, Tailwind CSS, and accessible project components.
3. Python 3.14, Django 5.2 LTS, Django REST Framework, and PostgreSQL 18 in every environment.
4. Same origin browser sessions with CSRF protection. No authentication token in browser local storage.
5. Patient, doctor, receptionist, and hospital administrator roles with default deny permissions.
6. Staff accounts are invitation only and require TOTP MFA. Patient self registration requires email verification.
7. UUID external identifiers, UTC storage, Asia/Dhaka display, E.164 phone values, and integer BDT minor units.
8. Administrative patient data only. No clinical notes, diagnosis, prescription, test, pharmacy, inpatient, insurance, or automated triage data.
9. Final queue token at check in. FIFO by check in time with explicit audited defer, restore, no show, completion, and override actions.
10. Adaptive arrival range based on observed service duration, with a configured fallback. It never changes medical priority.
11. In app and privacy safe email notifications through a database outbox and worker.
12. Onsite payment recording only. No card processing or storage.
13. Corrections and deactivation instead of silent deletion. Business state and audit history remain traceable.
14. MediQueue remains a development name until the hospital approves a production identity and trademark review.
15. Synthetic data only until every real data gate is signed.

## 13. Go live gaps

The following items are not supplied by the university reports or interface images. Each is a real data blocker unless the production acceptance record says otherwise.

1. Final hospital name, logo, address, departments, chambers, doctor roster, fees, hours, closures, support contact, and operational owner.
2. Signed doctor, receptionist, administrator, privacy, and technical acceptance for every critical workflow.
3. Qualified mapping to the Personal Data Protection Act 2026, National Data Management Act 2026, Cyber Security Act 2026, health sector duties, and any regulator or hospital policy.
4. Approved privacy notice, consent wording, retention schedule, data correction process, access request process, incident notification decision path, and vendor terms.
5. Production domain, DNS, Bangladesh based host, SMTP service, monitoring channel, backup destination, and named incident contacts.
6. Named staff accounts, verified invitations, MFA enrolment, least privilege review, and training evidence.
7. Passing unit, API, authorization, state, concurrency, browser, load, accessibility, dependency, container, and ASVS verification evidence.
8. A clean encrypted backup restoration meeting the one hour RPO and four hour RTO.
9. Successful staging deployment, migration rehearsal, rollback rehearsal, and deployment smoke record.
10. No unresolved critical or high security, privacy, integrity, backup, or access defect.
11. A controlled department pilot and daily review before wider hospital use.
12. A final production brand review because MediQueue is already used by healthcare products and the supplied logo has no documented ownership.

Until these gaps close, the correct release description is “production candidate using synthetic data,” not “production hospital system.”
