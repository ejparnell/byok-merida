# Durable Batched Application Analysis

Status: ready-for-agent

## Problem Statement

The Application Analysis dashboard presents its batch number as the number of Applications the operator expects to have analyzed, but the current synchronous flow treats that value as a queue-selection limit. Investigation established that the dashboard sends the selected value and the backend selects the full eligible batch. The observed loss happens later: DeepSeek thinking can consume the current 3,000-token generation allowance before producing final JSON, and the prompt asks for an unbounded Skill Signals list. In a real probe, the response ended for length with reasoning content but no usable analysis. The operator therefore sees only one usable Application Analysis, or none, even when requesting a larger batch.

The current flow also makes recovery and cost control unsafe. One browser request must remain open for the whole batch, transport retries and structured-output repairs have separate counters that can multiply provider calls, sent calls are not durably reserved or reconciled, and no run-level spend boundary exists. A disconnect or restart can leave Merida unable to distinguish an unbilled pre-transmission failure from an ambiguous paid call.

The operator needs the selected number to mean successful Analysis Completions, wants DeepSeek thinking to remain enabled at full standard quality, and requires every operator-initiated Analysis Run to remain within a hard $0.50 USD provider-spend ceiling.

## Solution

Replace the synchronous batch request with a durable, asynchronous Analysis Run. The operator selects an Analysis Batch Target—the number of successful Analysis Completions the run should pursue. At creation, Merida snapshots a fixed Run Candidate Set in canonical queue order containing at most twice the target. A background worker evaluates candidates sequentially, backfills past skipped and Candidate-Scoped Failures, and stops as soon as the target or another documented terminal condition is reached.

Persist run coordination metadata in an Applications-owned local SQLite Analysis Run Store. Notion remains authoritative for Applications and completed analyses. The store enables idempotent starts, one active run, single-flight provider work, automatic restart recovery, conservative handling of ambiguous sent calls, observable progress, and bounded cancellation without duplicating private Application or model content.

Make Merida's backend the Spend Enforcement Authority. Before every provider call, Cost Authorization atomically reserves the call's complete worst-case cost against a fixed 500,000-micro ceiling. Authorization uses the exact rendered request, conservative input bounds, an approved cache-miss rate, and the reasoning-inclusive output maximum. A call is never dispatched unless its full reservation is durable and fits. Reservations settle downward only from trustworthy evidence; uncertainty remains committed. Provider and gateway spending controls are defense in depth and are not required for Analysis readiness.

Keep DeepSeek thinking explicitly enabled at high effort with at most 8,000 generated tokens shared by reasoning and final JSON. Bound the visible response to exactly three summary sentences and an Analysis Signal Set containing three to ten concrete, evidence-backed Skill Signals. Validate signals independently so unsupported, generic, or duplicate signals can be discarded without wasting an otherwise valid paid response. Give each Application attempt one shared three-call budget across initial generation, transport recovery, and structured-output recovery.

Expose durable start, active-run lookup, run lookup, and cancellation through the dashboard API. The dashboard reconnects after reload and presents completion progress, candidate progress, Committed Spend, its constituent reservation categories, the terminal Analysis Run Outcome, and safe per-Application results.

## User Stories

1. As an operator, I want to select an Analysis Batch Target, so that I control how many successful Application Analyses a run pursues.
2. As an operator, I want the target to count Analysis Completions rather than attempted Applications, so that the number shown matches my intent.
3. As an operator, I want a newly produced Application Analysis to count toward the target, so that normal analysis work advances the run.
4. As an operator, I want a repaired existing Application Analysis to count toward the target, so that recovered work advances the run without another model call.
5. As an operator, I want a completion to require both a readable analysis body and finalized analysis properties, so that partial writes are not reported as complete.
6. As an operator, I want skipped Applications not to satisfy the target, so that ineligible work is not reported as analysis.
7. As an operator, I want failed Application attempts not to satisfy the target, so that failures do not inflate completion progress.
8. As an operator, I want the worker to backfill after a Candidate-Scoped Failure, so that one bad Application does not unnecessarily end the batch.
9. As an operator, I want backfill to remain finite, so that a run cannot consume an unbounded queue.
10. As an operator, I want the Attempt Budget to be twice the target and no larger than the available queue, so that the run has a predictable search boundary.
11. As an operator, I want each Application evaluated at most once per run, so that one difficult candidate cannot repeatedly consume work or spend.
12. As an operator, I want the candidate order fixed when the run is created, so that queue mutations do not produce surprising restart behavior.
13. As an operator, I want candidates revalidated immediately before use, so that Applications that are no longer eligible are not analyzed.
14. As an operator, I want a candidate that becomes ineligible to consume its fixed slot, so that the run remains deterministic.
15. As an operator, I want Applications that become eligible after run creation to wait for a later run, so that the current Run Candidate Set does not shift.
16. As an operator, I want the run to stop as soon as its target is met, so that no unnecessary paid call occurs.
17. As an operator, I want the run to report Attempt Budget exhaustion distinctly, so that I understand why backfill stopped.
18. As an operator, I want the run to report queue exhaustion distinctly, so that a small eligible queue is not confused with a failure.
19. As an operator, I want completed Applications preserved when a run ends partially, so that useful work is never rolled back.
20. As an operator, I want Run Analysis to return immediately with a durable run identity, so that I do not need to keep a long HTTP request open.
21. As an operator, I want analysis to continue after the browser disconnects, so that navigation or a transient network problem does not waste work.
22. As an operator, I want the dashboard to reconnect to an active run after reload, so that I can continue observing it.
23. As an operator, I want unfinished runs recovered after a backend restart, so that paid work and progress are not abandoned.
24. As an operator, I want finished and cancelled runs never to restart, so that terminal work is not repeated.
25. As an operator, I want only one Analysis Run active at a time, so that two tabs cannot create competing paid batches.
26. As an operator, I want a retransmitted start with the same idempotency key to return the same run, so that request retries cannot duplicate paid work.
27. As an operator, I want reusing an idempotency key with a different target rejected, so that one request identity never refers to two intentions.
28. As an operator, I want a different start during an active run to identify that run, so that the dashboard can follow it instead of creating another batch.
29. As an operator, I want an overlapping start not to queue or alter the active target, so that accepted work remains stable.
30. As an operator, I want to request cancellation of an active run, so that I can stop future provider calls.
31. As an operator, I want cancellation to preserve earlier completions, so that stopping a run does not undo valid work.
32. As an operator, I want a valid result from an in-flight call during cancellation committed and counted, so that completed paid work is not discarded.
33. As an operator, I want cancellation not to promise that an in-flight call can be stopped or refunded, so that spend reporting remains honest.
34. As an operator, I want a distinct cancelled outcome, so that cancellation is not confused with a technical defect.
35. As an operator, I want to see whether a run is queued, running, cancelling, or finished, so that its lifecycle is clear.
36. As an operator, I want every finished run to have one specific Analysis Run Outcome, so that I know why it stopped.
37. As an operator, I want ordinary Application failures not to mark the whole run failed, so that partial progress is represented correctly.
38. As an operator, I want the failed outcome reserved for unrecoverable Run-Scoped Failures, so that its severity is meaningful.
39. As an operator, I want to see completions against target, so that I can assess useful progress.
40. As an operator, I want to see evaluated candidates against Attempt Budget, so that I can assess remaining backfill capacity.
41. As an operator, I want safe per-Application results, so that I can distinguish analyzed, repaired, skipped, failed, and indeterminate work.
42. As an operator, I want Candidate-Scoped and Run-Scoped failures distinguished, so that I understand why the worker continued or stopped.
43. As an operator, I want one run's provider spend capped at $0.50 USD regardless of target, so that batch analysis has a predictable maximum cost.
44. As an operator, I want initial calls, retries, repairs, truncations, and ambiguous sent calls counted against the same ceiling, so that recovery cannot bypass it.
45. As an operator, I want every provider call authorized before transmission, so that cost is controlled before it can be incurred.
46. As an operator, I want the complete worst-case charge reserved atomically, so that recovery or concurrency cannot oversubscribe the ceiling.
47. As an operator, I want a call withheld when its reservation cannot fit, so that the run never knowingly exceeds its remaining authorized budget.
48. As an operator, I want a spend-limited outcome, so that stopping for cost is treated as a valid partial result.
49. As an operator, I want analysis quality preserved when spend runs out, so that Merida does not silently disable thinking or lower effort.
50. As an operator, I want an unknown or unverifiable model blocked before use, so that Merida does not guess at provider cost.
51. As an operator, I want analysis restricted to approved endpoint-and-model combinations, so that authorization uses known prices and output bounds.
52. As an operator, I want stale pricing approval to block new calls, so that old rates are not trusted indefinitely.
53. As a maintainer, I want approved pricing evidence reverified every 30 days, so that Cost Authorization uses recent information.
54. As a maintainer, I want pricing changed through reviewed configuration, so that runtime page scraping cannot silently redefine spend authority.
55. As an operator, I want authorization to assume cache-miss input pricing, so that uncertain discounts never make the reservation optimistic.
56. As an operator, I want the exact rendered provider request measured before authorization, so that all transmitted input is included.
57. As an operator, I want conservative tokenizer and UTF-8 byte bounds used for input, so that character-ratio guesses cannot understate cost.
58. As an operator, I want Job Content left complete, so that cost pressure does not silently truncate or summarize the source.
59. As an operator, I want oversized source content rejected before transmission, so that invalid context cannot create an avoidable charge.
60. As an operator, I want unaffordable source content to stop through the spend policy before transmission, so that no unauthorized charge occurs.
61. As an operator, I want all money represented in integer USD micros, so that floating-point rounding cannot weaken the ceiling.
62. As an operator, I want successful calls settled to trustworthy actual cost, so that unused reservation can fund later candidates.
63. As an operator, I want proven pre-transmission failures to release their full reservation, so that calls that could not incur cost do not waste budget.
64. As an operator, I want a valid settlement receipt to release only the proven unused part, so that conservative admission remains safe.
65. As an operator, I want missing or malformed settlement evidence treated conservatively, so that uncertainty cannot create imaginary budget.
66. As an operator, I want an ambiguous sent call's full reservation treated as consumed, so that a lost response is never assumed free.
67. As an operator, I want any retry after an ambiguous sent call separately authorized, so that recovery stays inside the same ceiling.
68. As an operator, I want Committed Spend shown as the primary spend value, so that active and indeterminate exposure is not hidden.
69. As an operator, I want verified cost, active reservations, indeterminate reservations, and remaining authorized budget shown separately, so that I can understand the conservative total.
70. As an operator, I want provider or gateway budget controls treated as additional protection, so that their absence does not block Analysis.
71. As an operator, I want Merida's backend to own spend enforcement, so that the solution does not depend on a no-overshoot provider feature that does not exist.
72. As an operator, I want thinking explicitly enabled, so that Application Analysis retains reasoning quality.
73. As an operator, I want high reasoning effort used consistently, so that recovery does not silently degrade analysis.
74. As an operator, I want no non-thinking fallback, so that successful runs meet the agreed quality contract.
75. As an operator, I want every provider call limited to 8,000 reasoning-inclusive generated tokens, so that output cost and completion time are bounded.
76. As an operator, I want exactly three summary sentences, so that analyses are concise and consistent.
77. As an operator, I want between three and ten valid Skill Signals, so that analysis remains useful without asking for unbounded output.
78. As an operator, I want required Skill Signals ordered before preferred and other useful signals, so that the most important evidence is visible first.
79. As an operator, I want near-duplicate signals merged, so that the limited set is not wasted on repetition.
80. As an operator, I want every Skill Signal tied to concrete Job Content evidence, so that Match Score remains grounded.
81. As an operator, I want unsupported, generic, and duplicate signals discarded independently, so that one bad signal does not force a full paid retry.
82. As an operator, I want the summary validated as a unit, so that malformed prose cannot be stored as complete analysis.
83. As an operator, I want a response accepted only when at least three valid signals remain, so that filtering cannot leave an unusable analysis.
84. As an operator, I want rejected signals excluded from Match Score and persistence, so that invalid evidence cannot affect downstream decisions.
85. As an operator, I want Match Score to describe fit against the prioritized Analysis Signal Set, so that its interpretation matches the bounded output.
86. As an operator, I want Resume Creation to keep reading complete Job Content independently, so that the bounded signal set is not treated as exhaustive requirements.
87. As an operator, I want each Application attempt limited to three provider calls total, so that one candidate cannot consume unbounded recovery cost.
88. As an operator, I want initial generation, transport recovery, and structured-output repair to share the same call budget, so that nested retry loops cannot multiply.
89. As an operator, I want a length-truncated or invalid response to consume a call slot, so that unsuccessful paid work is accounted for.
90. As an operator, I want transient transport, rate-limit, and provider-server errors to use only the current Application's remaining slots, so that recovery remains bounded.
91. As an operator, I want an exhausted systemic provider problem to stop the run, so that the same outage is not replayed across every candidate.
92. As an operator, I want authentication, balance, model, pricing, and spend-authorization defects to stop immediately, so that later candidates do not repeat a shared defect.
93. As an operator, I want candidate-specific source and output defects to permit backfill, so that healthy candidates can still complete.
94. As an operator, I want one provider call in flight at a time, so that spend reservations and target completion remain deterministic.
95. As an operator, I want sequential candidate processing, so that parallel calls cannot overshoot the target with unnecessary paid results.
96. As an operator, I want connection, inactivity, and absolute deadlines, so that a stuck provider call cannot occupy the worker forever.
97. As an operator, I want provider keep-alives unable to extend the absolute deadline, so that maximum call duration remains meaningful.
98. As an operator, I want a post-transmission deadline treated as indeterminate, so that uncertain billing is handled conservatively.
99. As an operator, I want provider calls non-streaming, so that the durable run rather than raw model tokens is the progress interface.
100. As an operator, I want finish reason, exact model identity, request identity, and usage captured, so that validation and Cost Settlement have evidence.
101. As an operator, I want reasoning content never persisted, logged, or exposed, so that private chain-of-thought data is not retained.
102. As an operator, I want Notion to remain authoritative for Applications and completed analyses, so that product records do not move into a coordination database.
103. As an operator, I want each completed Application committed independently, so that a later run problem cannot undo earlier work.
104. As an operator, I want the Analysis Run Store to contain coordination metadata only, so that private Application and model content is not duplicated locally.
105. As an operator, I want Analysis readiness to include model approval, valid pricing, and transactional reservation availability, so that unsafe work cannot begin.
106. As an API consumer, I want one canonical `target` field, so that successful-completion semantics are not confused with the old `limit` meaning.
107. As an API consumer, I want a durable run snapshot returned when work is accepted, so that I can follow progress without waiting for completion.
108. As an API consumer, I want an active-run lookup, so that a reloaded client can reconnect without retaining the run ID.
109. As an API consumer, I want a run lookup by identity, so that I can inspect current or terminal state.
110. As an API consumer, I want cancellation by run identity, so that the command targets exactly one durable run.
111. As an operator, I want the dashboard control labeled with Analysis Batch Target language, so that it describes successful completions rather than queue attempts.
112. As an operator, I want terminal outcomes and safe per-Application result codes visible, so that partial runs are understandable.
113. As a maintainer, I want crash recovery to reconcile or conservatively consume sent calls before dispatching new ones, so that restart cannot duplicate uncertain paid work.

## Implementation Decisions

- The Analysis Batch Target is the requested number of Analysis Completions, not the number of attempted Applications. Preserve the existing operator range of 1 through 10 and default of 5 while replacing the old semantic name.
- Newly generated and repaired analyses count as Analysis Completions. Failed and skipped candidates do not.
- An Analysis Completion requires a readable analysis body plus finalized `Analyzed` and Match Score properties. Existing body-first, properties-last persistence and repair behavior remains authoritative.
- The Attempt Budget is twice the target, bounded by the eligible queue at run creation. Each Application may consume at most one candidate evaluation per run.
- Run creation snapshots a canonically ordered Run Candidate Set containing only Application IDs and order. Canonical order remains Date Found ascending followed by the stable existing tie-breaker.
- Candidates are reloaded and revalidated immediately before evaluation. A newly ineligible candidate is skipped and consumes its fixed slot. Later additions and reorderings do not modify the set.
- One Application attempt has one shared Application Call Budget of three provider calls across initial generation, transport retries, and structured-output repairs.
- The Analysis Spend Ceiling is exactly 500,000 USD micros for every run, independent of target.
- Merida's backend is the Spend Enforcement Authority. Call admission and reservation are serialized and transactional against the run's remaining ceiling.
- A call's full worst-case reservation is durably stored before dispatch. The call is not sent when persistence, pricing, or authorization fails.
- Every initial call, repair, retry, truncation, failed sent call, and indeterminate sent call draws from the same run ceiling.
- Cost Authorization uses an Input Cost Bound, an 8,000-token reasoning-inclusive output bound, and approved cache-miss rates.
- The Input Cost Bound is derived from the exact rendered provider request and uses the greater conservative result of the pinned model tokenizer plus verified protocol overhead or the complete UTF-8 request byte count plus that overhead. Character-ratio estimates are not authoritative.
- Job Content is never silently truncated or summarized to fit context or spend. Content beyond the approved model context becomes a Candidate-Scoped Failure without transmission. Content that fits context but whose next call cannot fit the remaining run ceiling ends the run as `spend_limited`.
- Analysis may use only an exact endpoint and model combination in the reviewed local rate card. Each entry includes source evidence, cache-miss input rate, reasoning-inclusive output rate, output bound, verification date, and a validity window ending 30 days after verification.
- Runtime page scraping is not a pricing authority. Missing, expired, or unverifiable approval blocks readiness or recovery before a call.
- Provider unit-price filters and provider or gateway budget controls are used when supported as defense in depth. Their absence does not block readiness and they are not the authority for the guarantee.
- Monetary accounting uses integer USD micros with conservative ceiling rounding for authorization and exact receipt conversion for settlement.
- A proven pre-transmission failure releases its entire reservation. A valid provider or gateway receipt converts a reservation to verified cost and releases only the proven difference.
- Missing, malformed, mismatched, or unreconcilable settlement evidence leaves the full reservation consumed.
- A sent call with no reconcilable outcome becomes an Indeterminate Attempt. Its full reservation remains consumed, and a fresh call requires separate Cost Authorization and another call-budget slot.
- Application Analysis becomes a durable asynchronous Analysis Run rather than work scoped to the lifetime of its start request.
- The Applications context owns a local SQLite Analysis Run Store for coordination metadata and transactional reservations.
- The store persists run identity, idempotency identity and target, lifecycle state, terminal outcome, timestamps, leases, target and budget counters, candidate IDs and ordering, safe per-candidate states, call states, and spend reservations.
- The store never persists Job Content, Master Resume evidence, prompts, model reasoning, provider payloads, or generated analysis. Notion remains authoritative for Applications and completed analyses.
- Lifecycle states are `queued`, `running`, `cancelling`, and `finished`.
- A finished run has exactly one outcome: `target_met`, `spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `cancelled`, `authorization_blocked`, or `failed`.
- `authorization_blocked` covers authentication, balance, model approval, current pricing, and Spend Enforcement Authority readiness failures. `failed` is reserved for unsafe storage defects or exhausted systemic transport, rate-limit, or provider-server failures.
- If several stopping conditions coincide, an operator cancellation wins, then target met, then authorization or spend limitation, then candidate-set exhaustion. The selected outcome must describe the condition that prevented the next unit of work.
- Only one Analysis Run may be active, and only one provider call may be in flight.
- A repeated start with the same client-generated idempotency key and target returns the existing run without recreating candidates or calls. Reusing the key with a different target returns an idempotency conflict.
- A distinct start during an active run neither queues nor mutates work and returns a conflict containing the active run identity.
- Idempotency records are retained for at least as long as their corresponding run record. Historical pruning must never remove the key while a client could still observe that run.
- On backend startup, the worker reclaims queued runs and running or cancelling runs with expired leases. A healthy lease is not stolen.
- Recovery reconciles or conservatively consumes any previously sent call before authorizing another. Every new call is reauthorized with the current rate-card validity and remaining spend.
- A recovered run that no longer passes authorization finishes as `authorization_blocked`. Finished and cancelled runs do not resume.
- Cancellation prevents scheduling new calls but does not assume an in-flight call can be stopped or refunded. A valid in-flight result is committed and counted; an unreconciled one follows the indeterminate policy.
- Cancellation is idempotent. Repeating it while cancelling returns the current snapshot. Cancelling a finished run is a no-op that returns its terminal snapshot.
- Provider generation explicitly enables thinking at high effort and permits at most 8,000 generated tokens shared by reasoning and final JSON. Recovery never disables thinking, lowers effort, or raises this bound.
- Provider calls remain non-streaming. Transport uses a 10-second connection timeout, 120-second read-inactivity timeout, and five-minute absolute deadline. Provider keep-alives may maintain read activity but cannot extend the absolute deadline.
- The adapter captures finish reason, exact model identity, request identity, and usage metadata required for Cost Settlement. Reasoning content is never persisted, logged, or exposed. A deadline after transmission is indeterminate.
- The model-visible contract is exactly three summary sentences and no more than ten candidate Skill Signals. The accepted Analysis Signal Set contains three to ten concrete, evidence-backed signals.
- Required signals precede preferred signals, which precede other useful signals. Near-duplicates are merged deterministically.
- The summary validates as one unit. Skill Signals validate independently; unsupported, generic, and duplicate signals are discarded before scoring and persistence.
- A response completes without repair when its summary is valid and at least three valid signals remain after filtering. Otherwise it may consume another slot from the same Application Call Budget.
- Match Score is calculated locally from the accepted Analysis Signal Set and Master Resume evidence. Discarded signals never affect it.
- Resume Creation continues to read complete Job Content independently; the Analysis Signal Set is not an exhaustive downstream requirements contract.
- Candidate-specific source and output defects become Candidate-Scoped Failures after the Application Call Budget is exhausted and permit the worker to continue through the fixed set.
- Transient transport errors, `429` responses, and provider `5xx` responses may use the current Application's remaining call slots. Exhausting those slots on a systemic condition stops the run before the next candidate.
- The public start contract is `POST /api/v1/applications/analysis/run` with `target` and a client-generated `Idempotency-Key`. A new run returns `202` with its durable snapshot; an identical replay returns the existing snapshot.
- `GET /api/v1/applications/analysis/runs/active` returns the active run snapshot or an explicit null active run without error.
- `GET /api/v1/applications/analysis/runs/{runId}` returns current progress or the standard not-found error envelope.
- `POST /api/v1/applications/analysis/runs/{runId}/cancel` requests cancellation and returns the current durable snapshot. It is safe to repeat.
- The old `limit` field is removed from the start request rather than retained as an alias. The queue-preview query retains its pagination `limit`, which is unrelated to Analysis Batch Target.
- A run snapshot contains safe identity and timestamps; lifecycle state and optional outcome; target and Attempt Budget; completion, repaired, evaluated, skipped, failed, and indeterminate counts; Committed Spend, verified cost, active reservations, indeterminate reservations, and remaining authorized budget; and safe per-Application result entries. It contains no private source or model content.
- Per-Application result values are `analyzed`, `repaired`, `skipped`, `failed`, and `indeterminate`, paired with stable safe reason codes when applicable.
- The primary dashboard progress line shows completions against target, evaluated candidates against Attempt Budget, and Committed Spend against $0.50.
- Expanded spend detail separates verified cost, active reservations, indeterminate reservations, and remaining authorized budget. The UI never labels Committed Spend as actual cost.
- The dashboard checks for an active run on load, polls its durable snapshot while active, follows the run identity returned in a conflict, and never automatically repeats the start request.
- The Run Analysis control remains disabled while a run is active. Cancel is available for queued, running, and cancelling states. Terminal outcomes and safe per-Application results remain visible after completion.
- Polling cadence, lease duration, heartbeat frequency, SQLite schema layout, schema migration mechanics, and historical pruning intervals are implementation details, provided they satisfy the public lifecycle, recovery, privacy, and atomicity invariants in this specification.
- The existing workflow, route, frontend, AI-workflow, OpenAPI, generated-client, and operational documentation must be updated to describe the asynchronous target contract and remove the synchronous batch-limit contract.

## Testing Decisions

- Tests assert externally observable state transitions, dispatched-call records, public responses, persisted coordination invariants, and Notion-visible results. They do not assert private methods, SQLite table names, prompt prose, or incidental worker timing.
- The primary acceptance seam is the public FastAPI Analysis Run API through the normal application composition, using the real SQLite Analysis Run Store and background worker with deterministic workspace, provider, clock, rate card, tokenizer, and call barriers.
- Restart tests construct a fresh application instance over the same SQLite and workspace state. Concurrency tests use controlled provider barriers rather than timing sleeps.
- The primary seam covers run creation, idempotency, active-run conflict, polling, lifecycle, candidate selection, backfill, spend enforcement, settlement, cancellation, restart recovery, terminal outcomes, and Notion-visible completion.
- A focused recorded-provider seam verifies request details that the workflow double cannot prove: thinking enabled, high effort, 8,000-token output bound, non-streaming mode, timeout layers, finish reason, model and request identities, usage capture, and reasoning omission.
- The existing dashboard session and client seams cover start, active-run reconnection, polling, conflict recovery, cancellation, progress presentation, terminal refresh, and the rule against automatic POST replay.
- One focused persistence-contract test may inspect the real SQLite store to prove atomic one-active-run and reservation constraints and to verify the private-content denylist. Other behavior remains at the public seam.
- Existing public workflow contract tests are the prior art for endpoint schemas, HTTP statuses, technical error envelopes, queue movement, safe per-Application outcomes, OpenAPI, and generated-client compatibility.
- Existing execution and recovery tests are the prior art for overlapping work, provider barriers, revalidation, restart behavior, and content-free recovery metadata.
- Existing recorded DeepSeek tests are the prior art for transport retries, structured-output recovery, matching, and body-first persistence.
- Existing dashboard session and client tests are the prior art for interaction state and the no-automatic-POST-retry rule.
- The final behavior inventory is updated so every protected durable Analysis behavior has an owning regression.
- Test a target greater than one with enough healthy candidates and assert that processing continues until the target is met.
- Test that newly analyzed and repaired Applications both count as completions, while skipped and failed candidates do not.
- Test that a repair makes no provider call and still satisfies one target unit.
- Test that Candidate-Scoped Failures cause backfill within the fixed Run Candidate Set.
- Test that the set contains exactly the first `min(queue size, target × 2)` eligible IDs in canonical order.
- Test that queue additions, removals, and reorderings after creation do not alter the persisted set.
- Test that every candidate is reloaded and revalidated, a newly ineligible candidate consumes its slot, and no Application is evaluated twice.
- Test that the run stops immediately at target and does not dispatch a paid call for a later candidate.
- Test `target_met`, `spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `cancelled`, `authorization_blocked`, and `failed` as distinct observable outcomes.
- Test that ordinary candidate failures do not produce a failed run when another terminal outcome applies.
- Test that the start request returns `202` before provider work completes.
- Test that the same idempotency key and target returns one run and never duplicates candidates or calls.
- Test that the same idempotency key with a different target returns conflict without mutation.
- Test that a different key during an active run returns `409` with the active run identity.
- Test that start and worker-claim races cannot create two active runs or two in-flight provider calls.
- Test startup reclamation of queued and expired-lease runs, non-reclamation of a healthy lease, and non-reclamation of finished or cancelled work.
- Test crash windows before reservation, after reservation but before transmission, after transmission but before response persistence, and after response persistence but before settlement.
- Test that no call is dispatched until its complete reservation is durable.
- Test that a proven pre-transmission failure releases its reservation and a post-transmission ambiguous outcome retains the full reservation.
- Test that retry after an Indeterminate Attempt requires a second reservation and consumes another call slot.
- Test that Committed Spend never exceeds 500,000 USD micros under concurrent authorization attempts, retries, repairs, cancellation, and recovery.
- Test exact-boundary authorization and denial at one micro above the remaining ceiling.
- Test that verified cost, active reservations, and indeterminate reservations reconcile exactly to Committed Spend and conservative remaining budget.
- Test that valid settlement releases only proven unused reservation, while missing, malformed, mismatched, or unreconcilable usage releases none.
- Test exact integer-micro rounding at boundary values and ensure floating-point dollars are never used for authority.
- Test that cache-hit usage may affect settlement but never reduces pre-call authorization.
- Test both tokenizer and UTF-8 byte branches, including multibyte content and verified protocol overhead, and assert that the greater bound is used.
- Test that Job Content is neither truncated nor summarized when context or authorization fails.
- Test that an unknown endpoint or model, missing rate, expired approval, unavailable transactional store, or unaffordable call prevents provider dispatch.
- Test approval validity immediately before, at, and after 30-day expiration with a controlled clock.
- Test that external gateway-budget availability does not determine readiness.
- Test that thinking is explicitly enabled at high effort and generated tokens are capped at 8,000 for initial and recovery calls.
- Test that recovery never disables thinking, lowers effort, or raises the output bound.
- Test that transport retries and structured-output repairs share one three-call Application Call Budget and no fourth call occurs.
- Test that a `length` finish consumes a call slot and never persists incomplete output.
- Test acceptance of exactly three valid summary sentences and rejection of a malformed summary as a unit.
- Test that zero, one, or two valid signals cause bounded recovery, while three through ten valid signals can complete.
- Test that no more than ten signals are persisted and that required, preferred, and other useful signals appear in that priority order.
- Test deterministic removal of unsupported, generic, duplicate, and near-duplicate signals.
- Test that one invalid signal does not force recovery when a valid summary and at least three other valid signals remain.
- Test that discarded signals never affect Match Score or persisted analysis.
- Test that Resume Creation continues to consume complete Job Content independently of the bounded Analysis Signal Set.
- Test connection, read-inactivity, and absolute deadlines with a controlled transport and clock, including keep-alive activity that cannot extend the absolute deadline.
- Test that a deadline known to precede transmission releases the reservation and a deadline after transmission becomes indeterminate.
- Test that finish reason, exact model identity, request identity, and usage are available for settlement while reasoning never appears in SQLite, Notion writes, logs, API responses, or dashboard state.
- Test Candidate-Scoped handling for unusable source content and repeatedly invalid output.
- Test transient transport, `429`, and provider `5xx` recovery within the current Application's remaining call slots.
- Test that systemic exhaustion stops before dispatching against the next candidate.
- Test that authentication, balance, model, pricing, and Spend Enforcement Authority defects stop immediately as `authorization_blocked`.
- Test cancellation before dispatch, between candidates, during a valid in-flight result, and during an indeterminate in-flight result.
- Test that cancellation is idempotent and never rolls back earlier completions.
- Test dashboard presentation of completions, evaluated candidates, Committed Spend, verified cost, active reservations, indeterminate reservations, remaining budget, terminal outcome, and per-Application results.
- Test client and OpenAPI generation after replacing start-request `limit` with `target`, including rejection of the removed field and continued support for queue-preview pagination `limit`.

## Out of Scope

- Disabling thinking or falling back to non-thinking analysis.
- Silently lowering reasoning effort to fit token or spend constraints.
- Silently truncating or summarizing Job Content.
- Returning an exhaustive copy of every phrase or requirement in Job Content as Skill Signals.
- Streaming model tokens or reasoning to the dashboard.
- Persisting, logging, or exposing model reasoning.
- Parallel provider calls within one Analysis Run.
- Multiple simultaneous active Analysis Runs.
- Queuing a distinct second run behind an active run.
- Evaluating the same Application as a second candidate attempt within one run.
- Rolling back completed Applications when a later candidate fails, the run is cancelled, or spend is exhausted.
- Making an external provider or gateway budget the Spend Enforcement Authority.
- Requiring an external no-overshoot dollar-cap feature before Application Analysis can run.
- Runtime scraping of provider pricing.
- Assuming cache discounts during Cost Authorization.
- Moving Application or completed-analysis authority out of Notion.
- Storing Job Content, Master Resume evidence, prompts, provider payloads, reasoning, or generated analyses in the Analysis Run Store.
- Replacing local SQLite coordination with a distributed broker for the first implementation.
- Redesigning Resume Creation beyond preserving its independent use of complete Job Content.
- Replacing the deterministic evidence-based Match Score algorithm beyond limiting its input to the accepted Analysis Signal Set.
- Building or changing the feature as part of this specification-writing task.

## Further Notes

- The root cause is not lost UI serialization or a backend queue query that selects one item. Investigation verified that the selected batch value reaches the backend and the backend selects the requested eligible records.
- DeepSeek thinking is enabled by default. The failing probe ended for length after spending the 3,000-token generation allowance on reasoning and returned no usable final JSON. Increasing the allowance alone was insufficient; the successful probe paired an 8,000-token envelope with a ten-signal response bound.
- DeepSeek V4 maps `low` and `medium` reasoning effort to `high`, so this design explicitly selects `high` rather than relying on a misleading lower-effort setting.
- DeepSeek exposes no documented per-run dollar cap. Reviewed gateway budget mechanisms may allow an in-flight request to overshoot. The earlier external-enforcement prerequisite was therefore deliberately replaced with Merida-owned atomic worst-case admission; external limits remain defense in depth.
- The hard ceiling is enforced against approved, conservative unit prices and complete request bounds. Provider adherence to its published or contractually exposed prices remains an external billing assumption; where a provider exposes a request-level maximum unit-price filter, Merida must send it.
- The Applications glossary and its five ADRs are canonical for Analysis Batch Target semantics, the $0.50 ceiling, durable asynchronous execution, bounded output, and the public Analysis Run API. Implementation must update older synchronous workflow documentation rather than treating it as competing authority.
- The primary testing seam was chosen from existing repository test composition: public ASGI behavior with deterministic dependency injection. It is intentionally higher than the item graph or SQLite table shape.
- No implementation code was changed while producing this specification.
