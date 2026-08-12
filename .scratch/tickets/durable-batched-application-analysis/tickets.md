# Tickets: Durable Batched Application Analysis

Status: ready-for-agent

State: closed

Source: [Durable Batched Application Analysis](../../specs/durable-batched-application-analysis.md)

Build a durable Application Analysis flow that pursues successful Analysis Completions with thinking enabled while keeping every Analysis Run at or below a hard $0.50 USD provider-spend ceiling.

Work the **frontier**: any ticket whose blockers are all complete can start. [Produce one bounded thinking-enabled Analysis Completion](#1-produce-one-bounded-thinking-enabled-analysis-completion) and [Prefactor a durable Analysis Run ledger](#2-prefactor-a-durable-analysis-run-ledger) form the initial parallel frontier. The temporary compatibility introduced while expanding the start contract must disappear in the final contraction; the finished product has only the `target` start field and rejects the former `limit` field.

## 1. Produce one bounded thinking-enabled Analysis Completion

**What to build:** Make one healthy Application produce a concise, evidence-grounded Analysis Completion through the existing public Analysis flow, with DeepSeek thinking preserved at the agreed quality and output bounds.

**Blocked by:** None — can start immediately.

- [x] A healthy analysis request explicitly enables thinking at high effort, permits at most 8,000 generated tokens shared by reasoning and final output, and provides no non-thinking fallback.
- [x] The model-visible output contract asks for exactly three summary sentences and no more than ten candidate Skill Signals.
- [x] A stored Analysis Completion has one valid three-sentence summary and an accepted Analysis Signal Set containing between three and ten concrete, evidence-backed signals.
- [x] Required signals precede preferred signals, which precede other useful signals, and near-duplicates are merged deterministically.
- [x] The summary validates as a unit while signals validate independently; unsupported, generic, duplicate, and otherwise invalid signals are discarded without rejecting an otherwise usable paid response.
- [x] A response succeeds without a repair call when the summary is valid and at least three valid signals remain after filtering; a response with fewer than three valid signals does not become a completion.
- [x] Discarded signals are absent from persistence and cannot influence the locally calculated Match Score.
- [x] Completion still requires a readable analysis body and finalized `Analyzed` and Match Score properties, preserving the existing body-first, properties-last commit boundary.
- [x] Resume Creation continues to evaluate the complete Job Content independently rather than treating the bounded Analysis Signal Set as exhaustive requirements.
- [x] Provider reasoning is never persisted, logged, exposed through the public API, or included in operator-visible failures.
- [x] Public-flow tests exercise a healthy recorded provider response, independently discarded signals, an insufficient signal set, summary validation, final Notion-visible content, and the unchanged Resume Creation boundary.

## 2. Prefactor a durable Analysis Run ledger

**What to build:** Establish the durable, metadata-only coordination ledger needed to identify Analysis Runs, enforce atomic invariants, and recover work without moving authoritative Application content out of Notion. This is the intentional prefactor for the later asynchronous tracer bullets.

**Blocked by:** None — can start immediately.

- [x] The Applications context owns a local SQLite Analysis Run Store that can represent `queued`, `running`, `cancelling`, and `finished` lifecycle states.
- [x] A finished run has exactly one representable outcome: `target_met`, `spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `cancelled`, `authorization_blocked`, or `failed`.
- [x] The ledger persists run and idempotency identity, target, timestamps, leases, progress counters, ordered candidate identities, safe per-candidate states, provider-call states, and spend reservations.
- [x] Monetary values are stored as integer USD micros rather than floating-point values.
- [x] Database constraints and transactions enforce at most one active Analysis Run and make spend admission plus reservation atomic under concurrent attempts.
- [x] An unavailable or non-transactional store fails closed for any operation that would authorize provider work.
- [x] Idempotency identity is retained for at least as long as its corresponding observable run record.
- [x] The ledger never stores Job Content, Master Resume evidence, prompts, provider request or response payloads, generated analysis, or model reasoning.
- [x] Notion remains authoritative for Applications and completed analyses; the ledger stores coordination facts only.
- [x] Run snapshots can be projected from safe ledger facts without loading private source or model content.
- [x] A focused real-SQLite persistence test proves the one-active-run and atomic-reservation invariants and verifies the private-content denylist.

## 3. Bound one Application to three provider calls

**What to build:** Give one Application attempt a single inspectable budget of at most three actual provider transmissions across initial generation, transport recovery, and structured-output repair.

**Blocked by:** [Produce one bounded thinking-enabled Analysis Completion](#1-produce-one-bounded-thinking-enabled-analysis-completion).

- [x] The Application Call Budget counts actual transmissions to the provider, not graph invocations or higher-level attempts, and no fourth transmission can occur.
- [x] Analysis owns one recovery loop so the current transport retry behavior cannot multiply three workflow attempts into as many as nine HTTP calls; unrelated Resume Creation behavior remains unchanged.
- [x] Initial generation, transient transport retry, rate-limit retry, provider-server retry, and structured-output repair all consume slots from the same three-call budget.
- [x] Length-truncated, empty, malformed, and semantically invalid responses consume a call slot when they were transmitted.
- [x] Every recovery call retains thinking at high effort and the 8,000-token reasoning-inclusive generated-output ceiling; recovery never silently lowers quality.
- [x] Calls are non-streaming and use a 10-second connection timeout, 120-second read-inactivity timeout, and five-minute absolute deadline.
- [x] Provider keep-alives may maintain read activity but cannot extend the absolute deadline.
- [x] Safe call evidence distinguishes a proven pre-transmission failure from an ambiguous post-transmission failure and captures transmission state, finish reason, exact model identity, request identity, and usage metadata needed later for settlement.
- [x] A deadline after transmission is classified as indeterminate, and provider reasoning remains absent from call evidence, logs, persistence, and responses.
- [x] Public-flow and recorded-provider tests prove the exact wire envelope, mixed retry and repair sequences, timeout classifications, retained thinking settings, captured safe metadata, and the absence of a fourth transmission.

## 4. Authorize and settle one Application under the $0.50 ceiling

**What to build:** Make one Application analysis end to end only when Merida can durably reserve its complete worst-case provider cost under the run ceiling, then release budget solely from trustworthy settlement evidence.

**Blocked by:** [Prefactor a durable Analysis Run ledger](#2-prefactor-a-durable-analysis-run-ledger) and [Bound one Application to three provider calls](#3-bound-one-application-to-three-provider-calls).

- [x] Every Analysis Run has an Analysis Spend Ceiling of exactly 500,000 USD micros, independent of its target, and Committed Spend never exceeds that value.
- [x] Merida is the Spend Enforcement Authority: each initial, retry, repair, truncated, failed-sent, and indeterminate sent call receives a separate Cost Authorization before transmission.
- [x] Authorization durably stores the call's full worst-case reservation in the same serialized transaction that admits the call; no provider request starts before that transaction commits.
- [x] Concurrent authorization attempts cannot oversubscribe the run, an exact-boundary reservation is admitted, and a reservation one micro above the remaining ceiling is withheld.
- [x] Authorization is limited to an approved exact endpoint-and-model pair whose reviewed rate-card entry records source evidence, cache-miss input rate, reasoning-inclusive output rate and bound, verification date, and a validity window ending 30 days after verification.
- [x] Missing, expired, unknown, or unverifiable pricing, model approval, authentication, balance, or Spend Enforcement Authority readiness dispatches no call and produces a safe blocked result for later outcome mapping.
- [x] Pricing authority comes from reviewed configuration rather than runtime page scraping; provider unit-price filters and gateway budget controls are applied when supported only as defense in depth, and their absence does not block Analysis readiness.
- [x] The Input Cost Bound measures the exact rendered provider request and uses the greater conservative result of the pinned model tokenizer plus verified protocol overhead or the complete UTF-8 request byte count plus that overhead.
- [x] Authorization uses cache-miss input rates, the 8,000-token reasoning-inclusive output bound, integer-micro arithmetic, and conservative ceiling rounding; character-ratio estimates cannot authorize a call.
- [x] Job Content is neither truncated nor summarized to fit context or budget. Content beyond the approved model context is rejected without transmission; content that fits context but cannot fit the remaining spend is withheld without transmission.
- [x] A proven pre-transmission failure releases its entire reservation, while a valid matching provider or gateway receipt converts the reservation to verified cost and releases only the proven unused difference.
- [x] Missing, malformed, mismatched, or unreconcilable settlement evidence releases no reserved amount; an ambiguous sent call becomes an Indeterminate Attempt whose full reservation remains committed.
- [x] Any retry after an Indeterminate Attempt requires another slot from the same three-call budget and a fresh Cost Authorization against the remaining run ceiling.
- [x] Committed Spend is always the sum of verified cost, active reservations, and indeterminate reservations; cache-hit evidence may reduce settlement but never optimistic admission.
- [x] Public-flow tests with real SQLite and deterministic rate-card, tokenizer, clock, provider, and concurrency barriers cover multibyte input, exact and over-bound costs, stale and missing approvals, external-budget absence, reservation races, every settlement evidence class, and no-call blocked cases.

## 5. Expand with a durable Analysis Batch Target API

**What to build:** Add the durable asynchronous Analysis Run path and make it pursue a requested number of successful Analysis Completions through a fixed, finite Candidate Set. Keep the legacy start form only as temporary compatibility until its dashboard consumer migrates.

**Blocked by:** [Authorize and settle one Application under the $0.50 ceiling](#4-authorize-and-settle-one-application-under-the-050-ceiling).

- [x] `POST /api/v1/applications/analysis/run` accepts an Analysis Batch Target from 1 through 10, preserving the operator default of 5, and requires a client-generated `Idempotency-Key`.
- [x] A newly accepted start returns `202` with a durable run snapshot before provider work finishes, allowing analysis to continue after the initiating HTTP request or browser disconnects.
- [x] Repeating a start with the same idempotency key and target returns the same run without recreating candidates, reservations, or calls; reusing that key with a different target conflicts without mutation.
- [x] A distinct start during active work returns `409` with a typed conflict containing the active run identity and neither queues nor changes work.
- [x] `GET /api/v1/applications/analysis/runs/active` returns the active snapshot or an explicit null result without error; `GET /api/v1/applications/analysis/runs/{runId}` returns its current snapshot or the standard not-found envelope.
- [x] Run creation snapshots exactly the first `min(eligible queue size, target × 2)` candidate identities in Date Found ascending order followed by the existing stable tie-breaker.
- [x] Candidate additions, eligibility changes, and queue reorderings after creation never alter the fixed Run Candidate Set.
- [x] Immediately before evaluation, each candidate is reloaded and revalidated. A newly ineligible candidate is skipped, consumes its fixed slot, and does not satisfy the target.
- [x] Each candidate is evaluated at most once, candidates are processed sequentially, and only one provider call can be in flight.
- [x] A newly generated analysis and a repaired existing analysis each count as one Analysis Completion; a repair makes no provider call, while skips and failures do not satisfy the target.
- [x] A completion is counted only after its readable body and final properties have been committed independently to Notion; a later run problem cannot roll back prior completions.
- [x] Processing stops immediately when the target is met and creates neither a reservation nor a provider call for a later candidate.
- [x] Healthy and repair scenarios distinguish `target_met`, `attempt_budget_exhausted`, and `queue_exhausted` based on what prevented the next unit of useful work.
- [x] Safe run snapshots include identity and timestamps; lifecycle and optional outcome; target and Attempt Budget; completion, repaired, evaluated, skipped, failed, and indeterminate counts; all committed-spend categories; and safe per-Application entries without private source or model content.
- [x] The public API description, generated client, CORS handling for the idempotency header, and a minimal compatible dashboard boundary support the additive path while the richer dashboard migration remains pending.
- [x] Public acceptance tests use the normal application composition, real SQLite, deterministic collaborators, and a target greater than one to prove fixed ordering, repair-without-call, backfill, single-flight execution, idempotency, conflicts, immediate response, and exact stopping at the target.

## 6. Apply Candidate- and Run-Scoped failure policy

**What to build:** Make partial Analysis Runs predictable by allowing candidate-specific defects to backfill while stopping shared authorization, spend, provider, and storage failures at the correct run boundary.

**Blocked by:** [Expand with a durable Analysis Batch Target API](#5-expand-with-a-durable-analysis-batch-target-api).

- [x] Candidate-specific source defects and exhausted structured-output defects produce safe Candidate-Scoped Failures, consume that candidate's fixed slot, and allow the worker to continue.
- [x] Source content beyond the approved context is a Candidate-Scoped Failure with no transmission, while valid-context work whose next reservation cannot fit finishes the run as `spend_limited` before transmission.
- [x] Transient transport, `429`, and provider `5xx` conditions may use only the current candidate's remaining call slots; exhausting those slots on a systemic condition stops before evaluating another candidate.
- [x] Authentication, balance, model approval, current pricing, and Spend Enforcement Authority defects stop immediately as `authorization_blocked` without repeating the shared defect across candidates.
- [x] Unsafe storage defects and exhausted systemic transport, rate-limit, or provider-server failures finish the run as `failed`; ordinary Application failures never do.
- [x] Every finished run exposes exactly one of the seven Analysis Run Outcomes and one stable, safe reason code that describes what prevented the next unit of work.
- [x] Coincident stopping conditions use the specified precedence apart from cancellation: target met, then authorization or spend limitation, then candidate-set exhaustion.
- [x] Per-Application results distinguish `analyzed`, `repaired`, `skipped`, `failed`, and `indeterminate`, with stable safe reason codes where applicable.
- [x] Earlier completed Applications and their Notion records remain committed when any later candidate or run-scoped condition ends the run.
- [x] The worker never exceeds the fixed Candidate Set, one evaluation per candidate, the three-call Application budget, one in-flight call, or the 500,000-micro run ceiling while applying failure policy.
- [x] Public API tests cover every terminal outcome other than cancellation, every per-Application result, outcome precedence, candidate backfill, systemic early stop, context rejection, unaffordable work, and preservation of prior completions.

## 7. Recover unfinished paid runs after restart

**What to build:** Resume unfinished queued or running Analysis Runs after backend restart without abandoning progress, stealing healthy work, duplicating a paid transmission, or treating uncertain spend as free.

**Blocked by:** [Apply Candidate- and Run-Scoped failure policy](#6-apply-candidate--and-run-scoped-failure-policy).

- [x] Startup reclaims queued runs and running runs with expired leases, but never steals a healthy lease or resumes a finished run.
- [x] A fresh application instance over the same SQLite store exposes the same run identity, Candidate Set, progress, and spend state through the public API.
- [x] Recovery reconciles any previously sent call before authorizing another; it never duplicates a provider transmission or a completed Notion commit merely because the prior process stopped.
- [x] A crash before reservation leaves no spend, a durable reservation known not to have been sent is released, an unresolved sent call retains its full reservation as indeterminate, and a persisted valid response is settled and committed without retransmission.
- [x] Any recovery retry after an Indeterminate Attempt consumes another slot from the same Application Call Budget and obtains a fresh atomic reservation.
- [x] Every post-restart call is reauthorized against the current exact model approval, rate-card validity, remaining 500,000-micro ceiling, and transactional store readiness.
- [x] A recovered run that no longer passes authorization finishes as `authorization_blocked` without another transmission.
- [x] An unreconcilable sent call is never assumed free, and Committed Spend remains the conservative sum of verified, active, and indeterminate amounts after recovery.
- [x] Recovery continues to omit Job Content, prompts, provider payloads, generated analysis, and reasoning from the ledger and public snapshots.
- [x] Deterministic restart tests use fresh application instances, a controlled clock, persisted SQLite state, and provider barriers to cover crashes before reservation, after reservation but before send, after send but before response persistence, and after response persistence but before settlement.

## 8. Migrate the dashboard to durable Analysis Runs

**What to build:** Make the dashboard start, reconnect to, and clearly observe durable Analysis Runs using Analysis Batch Target semantics and conservative spend reporting.

**Blocked by:** [Apply Candidate- and Run-Scoped failure policy](#6-apply-candidate--and-run-scoped-failure-policy).

- [x] The control is labeled **Analysis Batch Target**, preserves the range 1 through 10 and default 5, and explains that the value represents successful Analysis Completions rather than attempted Applications.
- [x] Each intentional start generates one client idempotency key, and automatic transport behavior never replays the start POST.
- [x] An accepted `202` response causes the dashboard to follow its run identity; a typed active-run conflict causes it to follow that existing run without parsing an error message or issuing another start.
- [x] On load, the dashboard checks for an active run and reconnects; while work remains active, it polls the durable snapshot and keeps Run Analysis disabled.
- [x] The primary progress line shows completions against target, evaluated candidates against Attempt Budget, and Committed Spend against $0.50.
- [x] Expanded spend detail separates verified cost, active reservations, indeterminate reservations, and remaining authorized budget; Committed Spend is never presented as actual cost.
- [x] The interface distinguishes `queued`, `running`, `cancelling`, and `finished`, all seven terminal outcomes, and safe `analyzed`, `repaired`, `skipped`, `failed`, and `indeterminate` per-Application results.
- [x] Terminal results remain visible rather than being automatically dismissed, and reaching a terminal state refreshes affected queues without discarding the run result.
- [x] Dashboard and API state never exposes Job Content, prompts, provider payloads, generated analysis, or model reasoning.
- [x] The generated client, error normalization, dashboard adapter, session state, and UI remain compatible with the durable snapshot and typed active-run conflict.
- [x] Client and UI tests cover initial start, reload reconnection, polling, active conflict recovery, no POST replay, progress and spend presentation, partial outcomes, terminal persistence, and queue refresh.

## 9. Cancel an active Analysis Run safely

**What to build:** Let the operator stop future paid work from the dashboard while preserving completed Applications and honestly accounting for a call already in flight.

**Blocked by:** [Recover unfinished paid runs after restart](#7-recover-unfinished-paid-runs-after-restart) and [Migrate the dashboard to durable Analysis Runs](#8-migrate-the-dashboard-to-durable-analysis-runs).

- [x] `POST /api/v1/applications/analysis/runs/{runId}/cancel` makes cancellation available through the public API, generated client, dashboard session, and UI for `queued`, `running`, and `cancelling` runs.
- [x] Requesting cancellation prevents every not-yet-started provider call but does not promise that an in-flight call can be stopped or refunded.
- [x] A valid in-flight completion is committed and counted, an unreconcilable in-flight call becomes indeterminate with its full reservation committed, and all earlier completions remain intact.
- [x] Cancellation uses the same provider-call and reservation states as normal settlement and recovery rather than introducing a separate accounting path.
- [x] Repeating cancellation while a run is cancelling is idempotent and returns its current snapshot; cancelling a finished run is a no-op that returns its terminal snapshot.
- [x] When stopping conditions coincide, an operator cancellation has first precedence and the run finishes with the `cancelled` outcome.
- [x] Restart during `cancelling` resumes cancellation without scheduling new work, and a terminal cancelled run never resumes.
- [x] The dashboard exposes Cancel while a run is queued, running, or cancelling and continues to show its durable terminal result and conservative spend afterward.
- [x] Deterministic public-flow tests cover cancellation before dispatch, between candidates, during a valid in-flight completion, during an indeterminate in-flight call, repeated cancellation, restart while cancelling, and cancellation of a finished run.

## 10. Contract the synchronous batch-limit flow

**What to build:** Remove the temporary synchronous start contract after its dashboard consumer has migrated, leaving one canonical asynchronous Analysis Batch Target contract and current supporting documentation.

**Blocked by:** [Migrate the dashboard to durable Analysis Runs](#8-migrate-the-dashboard-to-durable-analysis-runs).

- [x] The Application Analysis start request accepts only the canonical `target` field and rejects the removed `limit` field rather than retaining it as an alias.
- [x] The unrelated queue-preview pagination `limit` remains supported and unchanged.
- [x] The former synchronous completed-or-blocked response, process-local batch coordination, compatibility types, and unused dashboard/session behavior are removed after all known consumers use durable run snapshots.
- [x] The public API description and generated client no longer expose the legacy synchronous start or response; the durable start and lookup contracts remain intact, and this contraction does not couple to the independently delivered cancellation contract.
- [x] Route, workflow, frontend, AI-workflow, architecture, operations, and generated-contract documentation no longer describe the synchronous batch-limit behavior.
- [x] Contract and behavior-inventory tests verify `target` semantics, `202` acceptance, legacy-field rejection, idempotency, active conflicts, safe snapshots, and the retained queue-preview pagination field.
- [x] The final regression gate proves Analysis still keeps thinking at high effort, respects the three-transmission Application budget, pursues multiple Analysis Completions, and never raises Committed Spend above 500,000 USD micros.
