# Adaptive Arrival Window and Fairness Audit

## 1. Purpose

The Adaptive Arrival Window gives a checked in patient a cautious estimate of when they should be near the chamber. The Fairness Audit proves how the queue order was formed and records every human exception.

The mechanism is intended to reduce uncertain waiting and crowding without turning an operational queue into medical triage. Its working principle is simple: give patients useful timing guidance while keeping every ordinary turn fair and explainable.

The implementation identifier for this specification is `aaw_v1`.

## 2. Boundary of the mechanism

### 2.1 What it does

1. Estimates a doctor’s usual service duration from recent completed visits.
2. Estimates the time before a waiting patient can be called.
3. Shows a range instead of pretending one exact time is guaranteed.
4. Recommends a conservative return window based on the earliest estimate and confidence.
5. Preserves first in first out order using actual check in and documented restore times.
6. Records the facts behind each order, estimate, defer, restore, no show, and override.

### 2.2 What it does not do

1. It does not diagnose, triage, score medical urgency, or recommend treatment.
2. It does not use symptoms, diagnosis, age, sex, disability, payment state, social status, or personal influence to change queue order.
3. It does not promise an appointment start time.
4. It does not replace onsite staff instructions or the hospital’s emergency procedure.
5. It does not train a machine learning model or send patient data to an external prediction service.
6. It does not allow a patient to see another patient’s name or identifier.

### 2.3 Prior art and originality claim

Appointment scheduling, numbered queues, rolling medians, median absolute deviation, estimated waiting time, idempotent writes, and audit logs are established techniques. This project does not claim to have invented any of them and does not claim to be a worldwide first.

The original project contribution is the particular production oriented combination used here: a privacy safe live queue, a small and inspectable median based estimate, a conservative return window, deterministic first in first out restoration, reasoned human overrides, staleness handling, and an audit record that can reproduce both the estimate and order. Any academic description must call this an original implementation combination and must not present it as proven clinical innovation or patented novelty.

## 3. Required data

### 3.1 Schedule input

For the appointment being served, `C` is the configured slot duration in minutes from the effective doctor schedule. Schedule validation permits whole minute values from 5 through 60 for this pilot.

If a legacy or corrected record falls outside that range, the calculation clamps `C` to 5 through 60 before use and records that normalization in the estimate input.

### 3.2 Service duration sample

A completed visit is a valid sample only when all of the following are true:

1. It belongs to the same doctor as the queue being estimated.
2. Its queue ticket reached `completed` through the normal service workflow.
3. Both `service_started_at` and `service_ended_at` exist.
4. `service_ended_at` is later than `service_started_at`.
5. The raw duration is at least 1 minute and no more than 240 minutes.
6. The record has not been marked invalid by an authorized correction with a recorded reason.

Cancellation, no show, defer time, time spent in `called`, missing timestamps, reversed timestamps, and an invalidated operational record do not become service samples.

The sample duration is the elapsed seconds from service start through service end divided by 60. Calculation uses decimal values, not binary floating point approximations.

### 3.3 Sample window

1. Select valid samples for the same doctor.
2. Sort them by `service_ended_at` descending, then by ticket UUID as a stable tie breaker.
3. Keep the latest 20 samples.
4. Let `n` be the number retained.
5. The schedule, location, department, patient identity, appointment source, and payment state do not alter the sample weight.

Using one doctor level sample keeps the pilot understandable and provides a usable fallback when a doctor works in more than one chamber. Later releases may study separate session models, but they must use a new calculation version and must not rewrite `aaw_v1` history.

## 4. Service duration estimate

### 4.1 Median

Let the retained valid durations in ascending order be `d1` through `dn`.

1. When `n` is odd, `M` is the middle duration.
2. When `n` is even, `M` is the arithmetic mean of the two middle durations.

### 4.2 Fallback

When `n` is less than 5, the estimated service duration `S` is the configured duration:

`S = clamp(C, 5, 60)`

This is the low confidence fallback. Recent observations are stored for later use but do not influence the estimate until the fifth valid completion.

### 4.3 Observed estimate

When `n` is at least 5, calculate:

`S_raw = (0.70 * M) + (0.30 * C)`

Then apply the required bound:

`S = clamp(S_raw, 5, 60)`

The clamp returns 5 when the raw result is below 5, 60 when it is above 60, and the raw result otherwise.

`S` remains a decimal number for later calculation. The patient facing point estimate is rounded to the nearest whole minute using round half up only after the complete wait calculation.

### 4.4 Confidence label

1. `low` applies when `n` is from 0 through 4 and the configured fallback is used.
2. `medium` applies when `n` is from 5 through 9.
3. `high` applies when `n` is from 10 through 20.

The label describes the amount of recent usable data, not a clinical confidence and not a guarantee of punctuality. Connection staleness is displayed separately and never hidden by a high label.

## 5. Observed variation

When `n` is at least 5, calculate median absolute deviation from the same retained sample:

1. For each sample, calculate `ai = absolute(di - M)`.
2. Sort the absolute deviations.
3. `MAD` is their median using the same odd and even rule as `M`.

The scaled observed spread is:

`V = 1.4826 * MAD`

The constant converts median absolute deviation to a robust standard deviation estimate when durations are roughly symmetric. The mechanism still treats the result as operational guidance, not a statistical guarantee.

When `n` is below 5, `MAD` and `V` are recorded as unavailable. The wider fallback range in section 7.3 is used.

## 6. Fair queue position

### 6.1 Effective waiting time

Every waiting ticket has `effective_waiting_at`.

1. At first check in, `effective_waiting_at` equals `checked_in_at`.
2. A late patient receives the actual check in time, not the scheduled appointment time.
3. A deferred ticket is excluded from selection.
4. When a deferred ticket is restored, `effective_waiting_at` becomes `restored_at`.
5. The original check in time, defer time, restore time, and original token remain unchanged in history.

### 6.2 Selection order

Eligible waiting tickets are ordered by:

1. Earliest `effective_waiting_at`.
2. Lowest token sequence when effective times are equal.
3. Ticket UUID as the final stable tie breaker if the first two fields are equal because of imported or corrected data.

The queue session is locked before selection. A session cannot have more than one ticket in the combined `called` or `in_service` position. Call next is unavailable until the active ticket starts and completes, is deferred, becomes no show, or is cancelled through a legal action.

### 6.3 People ahead

For a patient’s waiting ticket, people ahead consists of:

1. One active `called` or `in_service` ticket when it is not the patient’s own ticket.
2. Every eligible `waiting` ticket that sorts before the patient by section 6.2.

Deferred, completed, no show, and cancelled tickets are not counted. The displayed number is a count only. The response contains no other patient identity.

## 7. Wait range calculation

### 7.1 Current active service

Let `A` be the predicted remaining minutes for the queue’s active ticket.

1. When there is no active ticket, `A = 0`.
2. When the active ticket is `called` but service has not started, `A = S`.
3. When the active ticket is `in_service`, let `E` be the nonnegative elapsed minutes from `service_started_at` to calculation time. Then `A = max(0, S - E)`.
4. A clock inconsistency or future service start makes the estimate unavailable and raises an operational data warning. It is not silently converted into a plausible wait.

Let `W` be the number of eligible waiting tickets ahead of the patient, excluding the active ticket.

The unrounded point wait is:

`P = A + (W * S)`

The equivalent number of remaining service blocks is:

1. `Q = 0` when `P = 0`.
2. `Q = W + (A ÷ S)` when `P` is greater than 0.

The patient facing point estimate is `P` rounded to the nearest whole minute using round half up.

### 7.2 Observed range with at least five samples

When `n` is at least 5 and `P` is greater than 0, calculate uncertainty:

`U = max(5, V * square_root(max(Q, 1)))`

Then calculate the patient facing bounds:

`lower = floor(max(0, P - U))`

`upper = ceiling(P + U)`

The five minute minimum prevents an unrealistically narrow range when recent durations happen to be identical or have limited precision.

### 7.3 Wider fallback range

When `n` is below 5 and `P` is greater than 0, calculate:

`U = max(10, 0.50 * P, 0.50 * C * square_root(max(Q, 1)))`

Then use the same outward rounding:

`lower = floor(max(0, P - U))`

`upper = ceiling(P + U)`

This range is deliberately wider because the system has fewer than five usable completed visits for the doctor.

### 7.4 No one ahead

When `P` is 0, the wait range is 0 through 5 minutes and the guidance is to stay near the chamber now. This covers ordinary transition and staff response time without claiming an immediate call.

### 7.5 Ticket states without an active estimate

1. A `called` patient receives the instruction to report to the chamber now. The displayed wait is 0 minutes.
2. An `in_service` patient does not receive a waiting estimate.
3. A `deferred` patient receives no arrival window and is told to contact or follow staff guidance.
4. A `completed`, `no_show`, or `cancelled` patient receives the terminal state and no live estimate.
5. A closed, paused, inconsistent, or unavailable queue returns an explicit unavailable reason and last successful update. It never invents a number.

## 8. Recommended return window

The recommendation is derived from the lower wait bound so the patient is asked to return before the earliest reasonable call, not near the middle or upper end of the estimate.

### 8.1 Safety buffer

1. Low confidence uses a 20 minute safety buffer.
2. Medium confidence uses a 15 minute safety buffer.
3. High confidence uses a 10 minute safety buffer.

Let `B` be the applicable safety buffer and let `T0` be the calculation time.

Calculate:

`return_by = T0 + max(0, lower - B) minutes`

### 8.2 Window construction

1. If `return_by` is no more than 5 minutes after `T0`, the recommended window is `T0` through `T0 + 5 minutes` and the message is to stay nearby now.
2. Otherwise, the recommended window starts 5 minutes before `return_by` and ends at `return_by`.
3. The displayed values are converted from UTC to Asia/Dhaka after calculation.
4. A hospital policy that requires the patient to remain onsite takes priority. The interface must not advise a patient to leave the premises.
5. Every recommendation states that queue movement can change and that onsite staff instructions take priority.

The recommendation does not move the patient’s queue position. Returning early, late, or within the window does not change FIFO order automatically.

## 9. Snapshot and polling behavior

### 9.1 Patient snapshot

An authorized patient snapshot contains only:

1. The patient’s privacy safe token.
2. The currently served token.
3. The count of people ahead.
4. The rounded point wait and lower and upper wait bounds.
5. The recommended return window or state specific guidance.
6. The confidence label and valid sample count band, not raw patient samples.
7. The queue state.
8. The calculation version.
9. The server calculation time and last material queue event time.
10. A stale or unavailable indicator where applicable.

It does not contain another patient’s name, medical record number, appointment UUID, contact detail, age, sex, payment, or reason for an override.

### 9.2 Conditional requests

1. The server creates an `ETag` from the authorized snapshot projection, queue revision, calculation version, and current whole minute bucket where active service remaining time can change.
2. The browser sends `If-None-Match` with the next poll.
3. An unchanged authorized snapshot returns `304 Not Modified` without a response body.
4. The ETag is scoped to the authenticated projection and cannot be used as a cross patient cache key.
5. Patient queue responses use private no store caching headers even though conditional validation is supported.

### 9.3 Polling and staleness

1. A visible queue page polls every 10 seconds.
2. A page hidden by the browser visibility API polls every 30 seconds.
3. The page refreshes immediately when it becomes visible or the browser reconnects.
4. The page becomes stale after 30 seconds without a successful `200` or `304` response.
5. Stale status shows the last successful update and tells the patient to follow onsite staff guidance.
6. The page keeps the last safe snapshot during a temporary failure but never presents it as current.
7. A meaningful token or state change is announced once through an accessible live region. Routine polls are not announced.

## 10. Fairness Audit

### 10.1 Event record

Every queue transition records:

1. Queue session UUID and ticket UUID.
2. Privacy safe token and token sequence.
3. Previous state and new state.
4. Original check in time and current effective waiting time.
5. Actor UUID and active role.
6. Server time and request identifier.
7. Reason code and approved free text reason when required.
8. Queue revision before and after the action.
9. Whether the action followed ordinary FIFO or was an override.

The audit record uses internal identifiers for investigation and is not included in patient queue responses.

### 10.2 Estimate record

Each material estimate record stores enough information to reproduce the result:

1. Calculation version `aaw_v1`.
2. Calculation time.
3. Configured duration `C`.
4. Sample identifiers or a protected digest of the exact ordered sample set.
5. Sample count `n`, median `M`, `MAD`, spread `V`, and service estimate `S`.
6. Active ticket state, elapsed time `E`, remaining time `A`, waiting tickets ahead `W`, and service equivalents `Q`.
7. Point wait `P`, uncertainty `U`, rounded bounds, confidence, safety buffer, and return window.
8. Queue revision and whether an override or restore affected order.

Raw samples and protected identifiers are restricted to authorized operational review. Patient and general dashboard projections contain aggregate or banded data only.

### 10.3 Required reason actions

The following actions cannot commit with an empty reason:

1. Defer.
2. Restore or reinsert.
3. No show.
4. Cancellation after check in.
5. Manual invalidation of a service duration sample.
6. Any selection or placement that differs from ordinary FIFO.
7. Administrative correction of queue timestamps or state.

Reason text must remain operational and minimal. It must not become a place to store diagnosis, symptoms, clinical notes, accusations, or unnecessary personal details.

### 10.4 Override behavior

1. Ordinary call next never accepts a target ticket. It selects the FIFO ticket inside the locked transaction.
2. An override is a separate named action available only to an authorized doctor for their queue, an authorized receptionist, or an administrator.
3. The actor selects the affected ticket, an allowlisted operational reason category, and a concise explanation.
4. The interface shows the ordinary next token and the proposed effect before confirmation.
5. The transaction locks the queue and affected tickets, records the complete order before and after, applies the action once, and creates an audit event.
6. An override does not record or infer a medical priority. Clinical emergencies follow the hospital procedure outside the mechanism.
7. Repeated override requests remain idempotent.
8. An override cannot edit or delete an earlier queue event.

### 10.5 Automatic integrity check

At every ordinary call next, the service verifies that the selected ticket is the first eligible ticket by section 6.2. If the selected result differs, the transaction fails, no patient is called, and a high priority operational integrity event is raised.

The daily audit job also checks:

1. More than one called or in service ticket in one session.
2. Duplicate active tickets for one appointment.
3. Nonmonotonic token sequence.
4. A call that skipped an eligible earlier ticket without an override event.
5. Missing reasons for controlled exceptions.
6. Terminal tickets with later ordinary transitions.
7. Estimate records that cannot be reproduced from their stored inputs.

An integrity finding does not repair or delete history automatically. It creates a defect and requires authorized investigation.

## 11. Notification privacy

1. Queue email uses a general subject such as “Your hospital queue has an update.”
2. Email contains the patient’s own privacy safe token only when hospital policy approves it and otherwise directs the patient to the secure page.
3. Email never names the currently served patient, lists waiting patients, states symptoms, includes diagnosis, or exposes internal override reasons.
4. The secure link opens the same origin application and requires an authenticated authorized session before queue data are returned.
5. Delivery logs store recipient, template version, state, time, and safe provider reference. They do not store unnecessary rendered content.
6. In app notifications follow the same minimum information rule.

## 12. Evaluation metrics

Metrics are operational evidence, not medical outcome claims. They are calculated only after enough genuine pilot activity exists and under the approved retention and access policy.

### 12.1 Estimate accuracy

1. Point absolute error is the absolute difference between predicted wait `P` and actual minutes from estimate time to `called_at`.
2. Mean absolute error is the mean of valid point absolute errors for the reporting period.
3. Median absolute error is the median of the same errors and is the primary robust accuracy measure.
4. Bias is the median of predicted wait minus actual wait. A positive value means the mechanism tended to overestimate.
5. Interval coverage is the percentage of valid cases where actual wait falls from `lower` through `upper`, inclusive.
6. Interval width is the median of `upper - lower` so apparent coverage cannot be improved silently by making every range unhelpfully wide.

The main evaluation estimate is the first valid estimate recorded after check in. A secondary report may evaluate the most recent material estimate before call. Poll frequency never creates extra weight because ordinary `304` polls do not create evaluation observations.

Cases affected by defer, restore, manual override, queue closure, inconsistent timestamps, or terminal state before call are reported separately and are not mixed into the ordinary FIFO accuracy result.

### 12.2 Fairness and operational integrity

1. Override rate equals completed override actions divided by call events.
2. FIFO exception rate equals calls that did not select the ordinary first eligible ticket divided by call events. Every nonzero case must have an override event or becomes an integrity defect.
3. Restore count and median deferred time show how often patients leave and rejoin ordinary order.
4. No show rate and cancellation after check in rate are reported by queue session without exposing a patient identity.
5. Duplicate check in conflicts and simultaneous call conflicts show whether idempotency and locking controls are being exercised.

The pilot does not claim demographic fairness from these measures. It does not collect sensitive attributes merely to create a fairness chart.

### 12.3 Reliability

1. Stale snapshot rate is stale page transitions divided by active queue page observation periods.
2. Queue freshness is the elapsed time from a committed material queue event to the next successful visible patient refresh. The pilot maximum target is 15 seconds under the approved 50 concurrent user test.
3. Notification delivery rate is sent email jobs divided by terminal email jobs, with temporary retries reported separately.
4. Terminal notification failure count and age are operational alert measures.
5. Estimate unavailable rate records how often data quality or queue state prevented a responsible estimate.

### 12.4 Review cadence

1. Operations reviews integrity findings and terminal notification failures each service day.
2. The hospital administrator and delivery owner review queue, override, staleness, and accuracy metrics weekly during the controlled pilot.
3. A formula or threshold change requires documented evidence, hospital review, tests, a new calculation version, and a release. Historical estimates remain attached to their original version.

## 13. Failure and fallback behavior

1. Fewer than five valid doctor samples use configured duration and the wider low confidence range.
2. No active queue ticket uses zero active remaining time.
3. A missing or invalid configured duration makes the estimate unavailable until configuration is corrected.
4. A database, clock, or data integrity problem returns unavailable instead of an invented estimate and raises an operational event.
5. SMTP failure affects notification delivery only. The queue transaction and in app record remain committed.
6. Browser polling failure keeps the last safe snapshot, marks it stale after 30 seconds, and directs the patient to onsite staff.
7. During a full service outage, staff use the approved manual queue procedure. Recovery reconciles manual actions through authorized correction events instead of rewriting prior history.
8. If the estimate repeatedly misses the accepted operational range, staff may disable patient timing guidance through audited configuration while keeping token order and queue controls active.

## 14. Fixed calculation examples

These examples are required test vectors for `aaw_v1`. Implementations must reproduce them using decimal calculation and the rounding rules in this file.

### 14.1 Configured fallback example

Inputs:

1. `C = 15` minutes.
2. Four valid completed samples, so `n = 4`.
3. The active ticket is in service and has elapsed 5 minutes.
4. Two other waiting tickets sort before the patient, so `W = 2`.

Expected calculation:

1. `S = 15` and confidence is `low`.
2. `A = max(0, 15 - 5) = 10`.
3. `P = 10 + (2 * 15) = 40`.
4. `Q = 2 + (10 ÷ 15) = 2.666666...`.
5. Fallback `U = max(10, 20, 0.50 * 15 * square_root(2.666666...)) = 20`.
6. The wait range is 20 through 60 minutes.
7. The low confidence buffer is 20 minutes, so `return_by` is the calculation time. The recommended window is now through five minutes from now.

### 14.2 Observed median example

Inputs:

1. `C = 15` minutes.
2. Latest valid durations are 10, 12, 14, 14, 16, and 18 minutes.
3. The active ticket is in service and has elapsed 5 minutes.
4. Two other waiting tickets sort before the patient, so `W = 2`.

Expected calculation:

1. `n = 6`, `M = 14`, and confidence is `medium`.
2. `S = (0.70 * 14) + (0.30 * 15) = 14.3` minutes.
3. Absolute deviations are 4, 2, 0, 0, 2, and 4, so `MAD = 2`.
4. `V = 1.4826 * 2 = 2.9652`.
5. `A = max(0, 14.3 - 5) = 9.3`.
6. `P = 9.3 + (2 * 14.3) = 37.9`, displayed as 38 minutes.
7. `Q = 2 + (9.3 ÷ 14.3) = 2.650349...`.
8. `V * square_root(Q)` is approximately 4.827, so the five minute minimum applies and `U = 5`.
9. `lower = floor(37.9 - 5) = 32` and `upper = ceiling(37.9 + 5) = 43`.
10. The medium confidence buffer is 15 minutes, so `return_by` is 17 minutes after the calculation time. The recommended window begins 12 minutes after calculation and ends 17 minutes after calculation.

### 14.3 Upper clamp example

Inputs:

1. `C = 30` minutes.
2. Ten valid durations all equal 90 minutes.
3. There is no active ticket and one waiting ticket is ahead, so `W = 1`.

Expected calculation:

1. `n = 10`, `M = 90`, `MAD = 0`, and confidence is `high`.
2. `S_raw = (0.70 * 90) + (0.30 * 30) = 72`.
3. The required clamp gives `S = 60`.
4. `A = 0`, `P = 60`, and `Q = 1`.
5. The five minute minimum applies, so `U = 5`.
6. The wait range is 55 through 65 minutes.
7. The high confidence buffer is 10 minutes, so `return_by` is 45 minutes after calculation. The recommended window begins 40 minutes after calculation and ends 45 minutes after calculation.

### 14.4 No one ahead example

Inputs:

1. The patient is `waiting`.
2. There is no active ticket and no eligible waiting ticket ahead.

Expected result:

1. `P = 0` regardless of sample count.
2. The wait range is 0 through 5 minutes.
3. The recommendation is to stay near the chamber now.

### 14.5 Restore order example

Inputs:

1. Token 11 checked in at 09:00 and was deferred at 09:10.
2. Token 12 checked in at 09:05 and remains waiting.
3. Token 13 checked in at 09:12 and remains waiting.
4. Token 11 is restored at 09:15.

Expected order:

1. Token 12 has effective waiting time 09:05.
2. Token 13 has effective waiting time 09:12.
3. Restored token 11 has effective waiting time 09:15.
4. Ordinary call next order is token 12, then token 13, then token 11.
5. Token 11 retains its original 09:00 check in time and all defer and restore events in the audit record.

## 15. Required tests

1. Fewer than five samples always use configured duration.
2. Exactly five samples switch to the 70 percent median and 30 percent configured blend.
3. More than 20 samples use only the latest 20 by completion order.
4. Odd and even medians and MAD values are correct.
5. Reversed, missing, too short, too long, no show, cancelled, and invalidated records are excluded.
6. The service estimate clamps at 5 and 60 minutes.
7. Round half up, floor, and ceiling behavior match the fixed examples.
8. Active called, active in service, no active ticket, no one ahead, and elapsed time beyond `S` calculate correctly.
9. Low, medium, and high confidence boundaries occur at 0, 5, and 10 valid samples as documented.
10. Ordinary call next selects the earliest effective waiting time under concurrent requests.
11. Two simultaneous call next requests never activate two tickets.
12. A deferred ticket is excluded and a restored ticket joins behind all tickets already waiting.
13. Every controlled exception rejects a missing reason and creates immutable history when accepted.
14. An unauthorized user cannot read an estimate, sample, event, or audit record belonging to another patient or queue.
15. Patient snapshots never contain another patient’s identity or internal override reason.
16. ETag responses are scoped to the authorized projection and unchanged polls return `304`.
17. Visible, background, offline, reconnecting, and stale polling states follow the exact timing rules.
18. Accuracy, coverage, override, FIFO exception, staleness, and notification metrics reproduce known fixtures.

## 16. Limitations

1. A doctor’s recent median cannot predict an unusual consultation, interruption, emergency, or operational delay.
2. A small sample uses configured duration and produces intentionally broad guidance.
3. The 60 minute estimate cap can understate consistently longer services. The accuracy and bias reports must make this visible, and the hospital should correct scheduling or disable guidance rather than hide poor performance.
4. Doctor level sampling may not capture different visit types, locations, or sessions. The pilot avoids collecting clinical categories merely to improve prediction.
5. Median absolute deviation gives a robust range but does not prove a probability or service guarantee.
6. Polling can be delayed by device sleep, weak connectivity, server load, or an outage. Staleness is always shown.
7. A human override can be legitimate or misused. Reason capture and review improve accountability but do not prove fairness by themselves.
8. The mechanism measures operational order integrity, not demographic or clinical fairness.
9. The project must be evaluated with real operational data before any claim of reduced waiting, reduced crowding, or improved satisfaction is made.

## 17. Change control

1. The formula, sample validity rules, order rules, thresholds, buffers, or confidence labels cannot be changed as ordinary configuration in production.
2. A proposed change requires evidence, privacy review, hospital operational review, fixed test vectors, migration impact, and a new calculation identifier such as `aaw_v2`.
3. Historical estimate and fairness records remain attached to the version that produced them.
4. A release note explains the behavior change in plain language.
5. No change may add automated medical prioritization to this mechanism. That would be a separate clinical, legal, safety, and governance project outside the approved pilot.
