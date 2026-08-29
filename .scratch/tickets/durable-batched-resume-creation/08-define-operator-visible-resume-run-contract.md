# Define the operator-visible Resume Run contract

Parent: [Wayfinder: Durable Batched Resume Creation](map.md)

Type: grilling

Status: ready-for-agent

State: closed

Assignee: codex

Blocked by: [Classify Resume Run failures, outcomes, and cancellation](07-classify-resume-run-failures-and-cancellation.md)

## Question

What is the smallest safe public Resume Run contract that lets the dashboard intentionally start one Resume Batch Target, follow or reconnect to the active run, cancel it, understand progress, spend, partial and terminal results, and retain useful Resume, Resume Fit Analysis Note, and PDF outputs after completed Applications leave the queue and synchronous `POST /resumes/create` is removed?

The decision should settle idempotent `202` start and typed conflict behavior, active and by-ID lookup, cancellation, lifecycle and outcome vocabulary, progress and spend fields, safe per-candidate stages and reason codes, artifact summaries, retry eligibility, terminal-result rediscovery, retention, route operation IDs, generated-client impact, and the additive-to-contractive migration boundary without exposing private source, model, or recovery content.

## Decisions

- Unresolved Resume Artifact Quarantines are a first-class operator resource independent of Resume Run history. The public contract exposes a Resume Artifact Quarantine Worklist keyed by Resume Artifact Set ID, and run snapshots reference its entries rather than serving as their only discovery mechanism. The worklist remains discoverable after the owning run finishes and releases its active claim, including while a later unrelated Resume Run is active. It is not an acknowledgement queue and grants no force-clear, force-complete, or force-delete authority.
- Quarantine resolution exposes two distinct operator actions rather than one generic resolution command. Audited Resume Artifact Reconciliation freshly observes evidence and may return the original Artifact Set to Same-Run Artifact Recovery or seal a proven Resume Completion, but it never deletes artifacts. Resume Artifact Compensation is a separate explicit, idempotent authorization for strict verified cleanup and proceeds only while fresh evidence proves exact run ownership; it cannot mutate an independent artifact or a sealed Resume Completion. Neither action acknowledges away uncertainty or force-selects an outcome.
- Audited Resume Artifact Reconciliation and Resume Artifact Compensation are durable asynchronous actions. Each command first commits its operator intent, then returns `202 Accepted` with the current safe Artifact Set and quarantine snapshot; acceptance does not mean resolution finished. Work continues across process restart through the existing Resumes-owned durable authority, and the dashboard follows the stable Resume Artifact Set ID rather than holding the initiating HTTP request open. These actions do not introduce another Resume Run lifecycle state.
- Both quarantine action requests require a client-generated `Idempotency-Key` header and an `expectedRevision` body field copied from the last observed safe Artifact Set snapshot. The server resolves an existing idempotency binding before testing revision freshness: an exact replay reuses the original accepted intent and returns the current safe snapshot even when background work has advanced it, while reuse for another Artifact Set, action kind, expected revision, or other canonical request value returns typed `409 idempotency_conflict`. A new key whose expected revision is stale returns typed `409 resume_artifact_state_changed` with the current safe snapshot and performs no action. Every snapshot carries a monotonic integer `revision`; matching it is only an optimistic-concurrency guard, never ownership or mutation authority, so every action still performs fresh evidence and ownership validation.
- The public contract has no generic `retryEligible` field or retry action. Provider and artifact-effect recovery is automatic and bounded inside the owning workflow, terminal Resume Candidates never reopen within their run, and eligibility for a future run is determined only by the live Resume Creation Queue and later Resume Candidate Admission. A quarantined Artifact Set instead exposes a state-derived `availableActions` list containing only `reconcile`, `compensate`, or neither; the list describes safe current Resume Artifact Actions and never predicts future-run success.
- Reload-time terminal rediscovery uses `GET /api/v1/resumes/runs/latest`, which returns the most recently created Resume Run snapshot or `run: null` and is independent of active-run lookup. Latest is determined by immutable creation order, not `updatedAt`, so late spend settlement, quarantine reconciliation, or audited Resume Completion cannot reorder history. V1 adds no browsable Resume Run history: the dashboard is a process console, older known runs remain addressable by ID, Notion remains the completed-artifact record-management surface, and the separate Resume Artifact Quarantine Worklist carries unresolved attention from any run.
- V1 performs no automatic time-based pruning of safe Resume Run Snapshots, their bounded candidate and result summaries, Resume Artifact Set Snapshots, or start and Artifact Set action idempotency bindings. By-ID lookup and exact replay therefore remain valid, and an arbitrarily late audited quarantine seal or trustworthy spend settlement may update retained revisions. This is content-free logical retention, not retention of prompts, sources, provider payloads, canonical Resume or Note documents, or private checkpoints; checkpoint retirement remains governed by verified completion, compensation, and quarantine needs. Any future pruning policy requires an explicit contract migration rather than silently turning known run IDs, Artifact Set IDs, or keys into unknown resources.
- Starting a Resume Run requires the request body `{ "target": integer }` with an explicit Resume Batch Target from `1` through `10`; the public API supplies no omitted-value default. The dashboard may prefill its control with `5`, but it always sends the selected value. A missing, out-of-range, non-integral, or extra legacy `limit` field returns typed `400 invalid_request` before creating a Resume Run or idempotency binding. The `limit` query parameter on the separate Resume Creation Queue remains pagination only and is never an alias for the target.
- Starting a Resume Run requires a client-generated `Idempotency-Key`. A new key with no Active Resume Run atomically creates the run and binding and returns `202 Accepted` with its current durable snapshot. Binding lookup precedes readiness and the active-run check: exact key-and-target replay returns the original run's current snapshot with `202` even after it finishes, readiness changes, or a newer run becomes active; reuse with another target returns typed `409 idempotency_conflict`. A distinct key while a Resume Run is active returns typed `409 resume_run_active` with `activeRunId` and creates nothing. The single-active claim is Resumes-owned, so an independently authorized Application Analysis Run may overlap without either workflow sharing a target, ledger, or active-run conflict.
- For a new idempotency key, failed Resume Run Readiness returns typed `503 resume_run_not_ready` with one bounded safe `reasonCode` and applicable configuration or workspace-schema validation failures; it creates neither a run nor an idempotency binding. This pre-start error is distinct from the `authorization_blocked` Resume Run Outcome, which applies only when an existing run requires another provider call after authority is lost. Human-readable messages remain presentational and never carry raw provider errors or private content. Exact replay is resolved before this check and therefore returns its original run despite current readiness.
- When Resume Run Readiness succeeds but the eligible Resume Creation Queue is empty after active-quarantine exclusion, start still creates and idempotently binds a zero-candidate run. It returns `202 Accepted` with an immediately `finished` snapshot whose outcome and reason are `queue_exhausted`, whose Resume Candidate Set and Resume Attempt Budget are zero, and whose evaluations, completions, verified cost, active reservations, indeterminate reservations, and committed spend are zero; its fixed ceiling and full remaining authorization are still reported. This is not a readiness failure: it durably closes the operator's intentional request so replaying the same key after later queue additions cannot unexpectedly process new Applications.
- The core public route family is collection-shaped: `POST /api/v1/resumes/runs` (`startResumeRun`), `GET /api/v1/resumes/runs/active` (`getActiveResumeRun`), `GET /api/v1/resumes/runs/latest` (`getLatestResumeRun`), `GET /api/v1/resumes/runs/{runId}` (`getResumeRun`), and `POST /api/v1/resumes/runs/{runId}/cancel` (`cancelResumeRun`). The existing singular Application Analysis start route remains unchanged, but its path shape is not copied into this new resource family. Static `active` and `latest` routes are distinct from opaque run IDs, and the declared operation IDs are the generated-client compatibility names.
- Resume Artifact Quarantine discovery and resolution use the stable Artifact Set as their by-ID resource: `GET /api/v1/resumes/artifact-quarantines` (`listResumeArtifactQuarantines`), `GET /api/v1/resumes/artifact-sets/{artifactSetId}` (`getResumeArtifactSet`), `POST /api/v1/resumes/artifact-sets/{artifactSetId}/reconcile` (`reconcileResumeArtifactSet`), and `POST /api/v1/resumes/artifact-sets/{artifactSetId}/compensate` (`compensateResumeArtifactSet`). The worklist is an unresolved-only view; its entries reference the same Resume Artifact Set Snapshot returned by the by-ID route. That resource remains pollable when reconciliation clears quarantine, forward recovery resumes, or the set seals or compensates, so no disappearing quarantine-detail resource or separate resolution-job resource is added.
- `POST /api/v1/resumes/runs/{runId}/cancel` is intrinsically idempotent and requires no body or `Idempotency-Key`. A known run always returns `200 OK` with its current durable snapshot: an active run first commits cancellation and ordinarily reports lifecycle `cancelling`; queued cancellation may already report `finished`; and a finished run or run with an earlier winning stopping decision is returned unchanged. `200` means the command was handled, not that safe drain is complete, so clients follow `lifecycle` rather than HTTP status. An unknown ID returns typed `404 not_found` and no state is created.
- `ResumeRunSnapshot.outcome` and `reasonCode` are nullable only until the first durable stopping decision. That transaction sets both together, after which they are immutable even though lifecycle may remain `running` or `cancelling` during provider settlement, Artifact Set recovery, compensation, or quarantine drain. Every `finished` run has both fields. The public contract adds no duplicate `stopDecision`; lifecycle answers whether safe drain is complete, while outcome and reason answer why new scheduling stopped.
- Every Resume Run Snapshot embeds its complete fixed `candidates` array in immutable ordinal order. The Resume Candidate Set is bounded to at most 20 entries, so candidate pagination, cursors, and a second run-candidate route add no useful safety or payload benefit. Start, active, latest, by-ID, and cancel responses therefore share one self-contained snapshot shape; later updates change candidate facts and the snapshot revision but never membership, identity, or order.
- Run-level progress exposes only the independent authoritative counters `completions`, `candidatesConsidered`, and `evaluationsConsumed`; `target` and `attemptBudget` remain top-level fields, with `attemptBudget` equal to the fixed `candidates.length`. Consideration advances when a candidate receives its first durable disposition beyond `pending`, including the post-snapshot quarantine guard, while evaluation advances only when Resume Candidate Admission consumes the candidate. Candidate-state counts are derived from the complete array rather than duplicated in `progress`. `completions` is immutable per seal but may rise after lifecycle `finished` and may exceed `target` through audited late completion.
- Each candidate exposes a nullable coarse `stage` independent of its Resume Candidate State. The closed stage vocabulary is `admission`, `requirements`, `draft`, `artifact_recovery`, `completion_gate`, and `compensation`; untouched pending candidates and pre-admission quarantine-guard skips use `null`. A terminal candidate retains its latest entered stage for diagnosis. Provider attempt, retry, request, and response detail stays private, while post-Draft effect detail belongs to the referenced Resume Artifact Set Snapshot rather than multiplying candidate stages.
- Each candidate retains only `applicationId`, immutable `applicationLabel`, and `ordinal` as its durable Application presentation identity. `applicationLabel` is the safe `Role at Company` value captured with the run-start candidate snapshot; it remains unchanged and is never source, eligibility, ordering, naming, or ownership authority. The candidate does not retain or expose separate Company, Role, Match Score, Job URL, Job Content, Application Analysis, source observations, source proofs, or Notion read metadata. Completed output links belong to the separately verified Resume Completion Summary.
- Monetary accounting appears only in the run-level `spend` object as integer USD micros: `ceilingMicros`, `committedMicros`, `verifiedCostMicros`, `activeReservationMicros`, `indeterminateReservationMicros`, and `remainingAuthorizedMicros`. The invariants are `committedMicros = verifiedCostMicros + activeReservationMicros + indeterminateReservationMicros` and `remainingAuthorizedMicros = ceilingMicros - committedMicros`. No candidate-level amounts or API dollar strings are exposed; the dashboard applies the already-approved exact formatter. Trustworthy later settlement may reduce committed or indeterminate exposure and increase remaining authorization after lifecycle `finished`, incrementing snapshot revision without rewriting outcome or reason. `committedMicros` is never labeled actual cost or invoice amount.
- Beyond identity, `state`, nullable `stage`, and nullable `reasonCode`, each candidate exposes only `evaluationConsumed`, nullable `artifactSetId`, nullable `completion`, nullable `consideredAt`, `updatedAt`, and nullable `terminalAt`. `evaluationConsumed` makes the post-snapshot quarantine-guard exception explicit; `artifactSetId` is the stable link once a valid Draft establishes an Artifact Set; `completion` contains only atomically sealed result references; and the timestamps describe durable domain transitions rather than live request timing. Candidates expose no provider-call or artifact-effect attempt counts, leases, heartbeats, source fingerprints, checkpoint metadata, worker identities, or other operational diagnostics.
- Resume Artifact Set disposition is independent of candidate state and quarantine and uses exactly four values: `recoverable` while the original set may still complete forward, `compensation_required` once completion is definitively impossible and exact-owned effects must be reversed, `sealed` once Resume Completion is durably committed, and `compensated` once strict verified reversal is finished. Quarantine remains a separate nullable mutation lock, so either nonterminal disposition may be quarantined; the contract has no `quarantined` disposition. `sealed` and `compensated` are terminal and cannot transition back to a nonterminal disposition.
- Each Resume Artifact Set Snapshot exposes one nullable `pendingBoundary`: the earliest canonical artifact boundary not yet freshly verified and durably recorded. Forward recovery uses `stage_pdf`, `create_resume`, `publish_pdf`, `create_note`, `validate_completion`, and `attach_relation`; strict compensation uses `clear_relation`, `archive_note`, `remove_published_pdf`, `archive_resume`, and `remove_staged_pdf`. Committing intent or dispatching an effect does not advance the boundary—exact observation and verification do—so the field never claims external success from a request or stale journal phase. Quarantine may lock the current boundary without changing it, and terminal `sealed` or `compensated` sets use `null`.
- An accepted asynchronous quarantine action appears in its Artifact Set Snapshot as nullable `activeAction: { kind, acceptedAt }`, where `kind` is `reconcile` or `compensate`. At most one action is active per Artifact Set. Acceptance atomically increments `revision`, sets `activeAction`, and empties `availableActions`; the slot survives restart and clears only when the action durably settles, after which availability is recomputed from fresh state. A new idempotency key submitted against the current revision while the slot is occupied returns typed `409 resume_artifact_action_active` with the current snapshot, while exact replay still resolves first and returns the snapshot for its accepted intent. The contract exposes no action ID, queued-versus-running substate, percentage, cancellation endpoint, or worker diagnostic.
- `ResumeArtifactSetSnapshot.quarantine` is nullable and, when present, contains only `reasonCode`, `enteredAt`, and `lastAssessedAt`. Its closed reason vocabulary is `artifact_checkpoint_unavailable`, `artifact_ownership_unproven`, `artifact_content_mismatch`, `artifact_relation_unproven`, `artifact_result_unreconstructable`, and `artifact_compensation_unproven`. Both timestamps are set from the assessment that opens the episode; `enteredAt` then marks the start of that uninterrupted episode, while `lastAssessedAt` advances only after a later durable evidence-backed assessment, including one that leaves the reason unchanged, and is never earlier than `enteredAt`. The projection exposes no evidence payload, digest, external identity detail, filesystem path, raw error, free-form message, or quarantine history. `availableActions` and `activeAction` remain sibling Artifact Set fields rather than members of the nullable quarantine object.
- In addition to its disposition, pending boundary, quarantine, action, and eventual result fields, each standalone Artifact Set Snapshot carries only `artifactSetId`, `runId`, `applicationId`, `candidateOrdinal`, immutable `applicationLabel`, `revision`, `createdAt`, and `updatedAt`. `createdAt` is the Draft-to-Artifact transaction time; `updatedAt` advances with every safety-relevant Artifact Set revision. `revision` is monotonic and may advance even when the coarse public fields otherwise render identically, ensuring that operator actions cannot race a hidden evidence or ownership change. The resource has no separate candidate ID, live Application metadata, Resume Run outcome, Notion identity, digest, or storage path.
- Both a run candidate and its Artifact Set Snapshot expose the same nullable `completion` object containing `sealedAt`, required `resume: { id, url }`, required `note: { id, url }`, and required `pdf: { filename, downloadUrl }`. It becomes non-null only in the atomic `sealed` transition; partial results and nullable members cannot escape before that proof. The stable PDF URL targets `GET /api/v1/resumes/artifact-sets/{artifactSetId}/pdf` (`downloadResumeArtifactSetPdf`), making Artifact Set identity rather than a Notion Resume page ID the durable download authority. The summary excludes duplicated titles, Company or Role, digests, transient paths, and raw artifact content.
- The finalized PDF basename is exactly `{Company}-{Role}-{User}.pdf`. Each component is Unicode NFKC-normalized; Unicode letters, numbers, and combining marks are preserved; every other maximal run becomes one hyphen; surrounding hyphens are removed; case is preserved; and the result is truncated to at most 64 UTF-8 bytes without splitting a code point before trailing hyphens are removed again. An empty normalized Company or Role fails the candidate's existing source-validity admission boundary, while an empty normalized configured User fails Resume Run Readiness; no placeholder component is invented. Joining three valid components with two hyphens and `.pdf` yields at most 198 UTF-8 bytes. The exact basename is persisted when the Artifact Set is established and never changes after source or configuration edits; it remains presentation-only while ownership and storage are keyed by Artifact Set ID.
- `ResumeRunSnapshot` has exactly the top-level fields `runId`, monotonic `revision`, `lifecycle`, nullable `outcome`, nullable `reasonCode`, `target`, `attemptBudget`, `createdAt`, nullable `startedAt`, nullable `stoppingDecidedAt`, nullable `finishedAt`, `updatedAt`, `progress`, `spend`, and the complete `candidates` array. `startedAt` remains null when a zero-candidate or pre-start-cancelled run never begins execution; `stoppingDecidedAt` is committed with outcome and reason; `finishedAt` marks completed safe drain; and `updatedAt` plus `revision` may advance after it for audited late completion or trustworthy spend settlement. The snapshot duplicates no status, percentage, ETA, active-candidate pointer, queue count, error list, or worker metadata.
- The public schema imports ticket 07's Resume Run Lifecycle, Resume Run Outcome, Resume Candidate State, reason-presence rules, and complete bounded reason registry without aliases or reinterpretation. Candidate `ordinal` values are zero-based, every timestamp is an RFC 3339 UTC instant, and all public enums are closed OpenAPI unions rather than unconstrained strings. Run and Artifact Set revisions begin at one. Run revision advances whenever its public snapshot changes; Artifact Set revision advances on every committed safety-relevant mutation, including a hidden evidence change whose coarse projection otherwise renders identically.
- Successful JSON routes retain Merida's generated-client envelope conventions: `ok: true` with empty `validationFailures` and `errors`, followed by their named payload fields. Active and latest lookup use nullable `run`; by-ID and command responses do not. The quarantine worklist returns complete Artifact Set Snapshots ordered by current `quarantine.enteredAt` ascending and `artifactSetId` ascending, with opaque cursor pagination, default `limit=20`, and an allowed range of 1 through 50. It exposes no mutable total count because entries may resolve between pages.
- Typed API errors remain sanitized CommonResponse errors. Request syntax and unsupported legacy fields use `400 invalid_request`; malformed worklist cursors use `400 invalid_cursor`; unknown run or Artifact Set IDs on JSON resource and action routes use `404 not_found`; an unknown, unsealed, missing, or digest-invalid PDF uses `404 pdf_not_found`; start and action idempotency mismatches use `409 idempotency_conflict`; and the already-defined active-run and Artifact Set conflicts use their specific codes. A state-changing Artifact Set conflict includes the current safe snapshot as sibling `artifactSet`, while `resume_run_active` exposes only `activeRunId`. Start readiness uses `503 resume_run_not_ready` with a bounded `reasonCode`; later temporary coordination loss uses sanitized `503 resume_coordination_unavailable`; unexpected defects use `500 internal_error` with a request ID. Raw exception, provider, source, checkpoint, path, and evidence detail never enters these envelopes.
- A fresh, current-revision Artifact Set action whose `kind` is absent from `availableActions` returns typed `409 resume_artifact_action_unavailable` with the current snapshot. Artifact action precedence is syntactic validation, existing idempotency binding, Artifact Set existence, expected revision, active action, then current availability. Start precedence is syntactic validation, existing idempotency binding, Active Resume Run, Resume Run Readiness, then the atomic queue snapshot and run creation. These orders make exact replay stable while preventing stale operator intent from acquiring authority.
- An Artifact Set action binding permanently records its Artifact Set, action kind, canonical request including expected revision, accepted revision, and acceptance time. Exact replay confirms only that this historical intent was durably accepted; the returned Artifact Set is deliberately its current snapshot and may describe a later revision, settled action, or later quarantine episode. Clients follow the stable Artifact Set ID and revisions rather than interpreting a replayed `202` as proof of the original action's result.
- The current Resume Artifact Quarantine remains the Application-scoped mutation lock for the complete lifetime of `activeAction`, including forward recovery resumed by reconciliation. The Resume Creation Queue and pre-admission guard therefore continue to exclude that Application until the action atomically reaches a sealed or compensated terminal set, or stops under an unresolved quarantine with no automatic mutation active. Clearing the original uncertainty never creates a window in which another run may admit the same Application while the original set is still mutating.
- Artifact Set actions neither acquire nor conflict with the single Active Resume Run claim. They may be accepted for distinct quarantined Applications while an unrelated Resume Run is active; the retained Application-scoped quarantine lock, not a global scheduling block, prevents unsafe overlap on the same Application. Execution may remain internally serialized without changing accepted command semantics.
- V1 uses ordinary polling of stable resource IDs, not streaming, long polling, webhooks, or a resolution-job resource. Dynamic JSON responses are not cacheable; clients compare `revision`, poll a run while it has not finished, poll an Artifact Set while `activeAction` is non-null, refresh the quarantine worklist for cross-run attention, and refetch the owning run after an Artifact Set action settles. Exact cadence, backoff, visibility-pausing, and dashboard copy belong to ticket 09.
- Ordinary run, Artifact Set, and worklist reads project durable coordination only and perform no live Notion or PDF validation. V1 adds no `historicalDrift` field or historical-repair action. The Artifact-Set PDF download performs exact index, Artifact Set, path-containment, and byte-digest verification before serving; a missing or mismatched sealed PDF reports `pdf_not_found` without rewriting its immutable Resume Completion. This is a read-only observation of Historical Artifact Drift, not Same-Run Artifact Recovery.
- V1 applies no automatic time-based pruning to a sealed Artifact Set's digest-verified published PDF while its retained Completion Summary exposes that download. There is no public deletion action. Verified compensation may remove only an unsealed run-owned PDF under ticket 05, while later manual or external removal of a sealed PDF is Historical Artifact Drift and fails closed at download.
- Migration is additive in implementation but contractive at the supported public cutover. Durable stores and routes may land behind an internal boundary first; one coordinated API, committed OpenAPI/generated-client, and dashboard release then exposes the Resume Run contract and removes `POST /api/v1/resumes/create`, `GET /api/v1/resumes/{resumeId}/pdf`, and their generated `CreateResume*` and `DownloadResumePdf*` symbols. No release supports two public Resume writers, no `410` compatibility adapter is promised, and removed paths return ordinary route-not-found behavior. Target `1` is the canonical replacement for the former single-row operation.

## Answer

Expose Resume Creation as one retained, revisioned Resume Run resource plus independently retained Resume Artifact Set resources. Starting, cancelling, reconciling, and compensating commit durable intent before returning; the dashboard follows stable IDs with generated-client polling rather than tying truth to one HTTP request. One complete run snapshot reports the fixed candidates, separate lifecycle and stopping decision, exact progress and committed-spend constituents, safe candidate detail, and atomically sealed outputs. An unresolved-quarantine worklist preserves operator attention after the owning run finishes, while separate evidence-gated reconciliation and compensation commands prevent generic retry or acknowledgement from becoming mutation authority.

The supported cutover replaces the synchronous row-level writer and Resume-ID PDF route. Public state remains content-free, retained without V1 time pruning, and explicit about the unusual truth that a finished run's outcome is immutable while its revision, spend settlement, and audited late completions may still advance.

## Problem Statement

The current `POST /api/v1/resumes/create` response makes one request both execution lifetime and result memory. It cannot truthfully represent restart, idempotent reconnect, cancellation drain, conservative spend, a fixed backfill budget, or an Artifact Set whose ambiguity outlives its run. Completed Applications also leave the Resume Creation Queue, so queue refresh cannot be terminal-result history. Reusing the legacy response would either hide durable work, expose private recovery detail, or create a competing write path around the Resume Run authority.

The contract therefore needs three independently addressable truths:

1. the operator's bounded Resume Run and its fixed candidate history;
2. each run-owned Resume Artifact Set and any evidence-gated action still affecting it; and
3. the unresolved Resume Artifact Quarantine worklist, which is attention state rather than run history.

## Solution

### Routes and response models

| Method and route | Operation ID | Success | Response |
| --- | --- | --- | --- |
| `GET /api/v1/resumes/queue` | `getResumeCreationQueue` | `200` | existing `GetResumeCreationQueueResponse` |
| `POST /api/v1/resumes/runs` | `startResumeRun` | `202` | `ResumeRunResponse` |
| `GET /api/v1/resumes/runs/active` | `getActiveResumeRun` | `200` | `ResumeRunLookupResponse` with nullable `run` |
| `GET /api/v1/resumes/runs/latest` | `getLatestResumeRun` | `200` | `ResumeRunLookupResponse` with nullable `run` |
| `GET /api/v1/resumes/runs/{runId}` | `getResumeRun` | `200` | `ResumeRunResponse` |
| `POST /api/v1/resumes/runs/{runId}/cancel` | `cancelResumeRun` | `200` | `ResumeRunResponse` |
| `GET /api/v1/resumes/artifact-quarantines` | `listResumeArtifactQuarantines` | `200` | `ResumeArtifactQuarantineListResponse` |
| `GET /api/v1/resumes/artifact-sets/{artifactSetId}` | `getResumeArtifactSet` | `200` | `ResumeArtifactSetResponse` |
| `POST /api/v1/resumes/artifact-sets/{artifactSetId}/reconcile` | `reconcileResumeArtifactSet` | `202` | `ResumeArtifactSetResponse` |
| `POST /api/v1/resumes/artifact-sets/{artifactSetId}/compensate` | `compensateResumeArtifactSet` | `202` | `ResumeArtifactSetResponse` |
| `GET /api/v1/resumes/artifact-sets/{artifactSetId}/pdf` | `downloadResumeArtifactSetPdf` | `200` | `application/pdf` |

All JSON success models extend the repository's `CommonResponse`: `ok` is true and `validationFailures` and `errors` are empty. `ResumeRunResponse.run` and `ResumeArtifactSetResponse.artifactSet` are non-null. `ResumeRunLookupResponse.run` is nullable. The worklist response contains `items: ResumeArtifactSetSnapshot[]` and `pagination: { limit, nextCursor, hasMore }`. The existing Resume Creation Queue remains the preview surface and retains its existing payload and pagination contract; its `limit` never becomes a run target.

Start accepts only:

```text
Idempotency-Key: 1..255 characters matching ^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$
body: { target: integer from 1 through 10 }
```

Reconciliation and compensation accept only:

```text
Idempotency-Key: the same safe key grammar
body: { expectedRevision: integer >= 1 }
```

Cancellation accepts no body and no idempotency header. JSON models forbid unknown fields.

### Resume Run Snapshot

```text
ResumeRunSnapshot {
  runId: string
  revision: integer >= 1
  lifecycle: "queued" | "running" | "cancelling" | "finished"
  outcome:
    | "target_met"
    | "spend_limited"
    | "attempt_budget_exhausted"
    | "queue_exhausted"
    | "cancelled"
    | "authorization_blocked"
    | "failed"
    | null
  reasonCode: ResumeReasonCode | null
  target: integer 1..10
  attemptBudget: integer 0..20
  createdAt: timestamp
  startedAt: timestamp | null
  stoppingDecidedAt: timestamp | null
  finishedAt: timestamp | null
  updatedAt: timestamp
  progress: {
    completions: integer >= 0
    candidatesConsidered: integer >= 0
    evaluationsConsumed: integer >= 0
  }
  spend: {
    ceilingMicros: integer >= 0
    committedMicros: integer >= 0
    verifiedCostMicros: integer >= 0
    activeReservationMicros: integer >= 0
    indeterminateReservationMicros: integer >= 0
    remainingAuthorizedMicros: integer >= 0
  }
  candidates: ResumeRunCandidate[]
}
```

`attemptBudget` always equals `candidates.length`, which is fixed at `min(run-start eligible queue size, target × 2)`. Candidates are complete, zero-based, immutable in membership and ordinal order, and bounded at 20. `outcome`, `reasonCode`, and `stoppingDecidedAt` are either all null or all non-null; their first non-null values are immutable. `finishedAt` is non-null exactly when lifecycle is `finished`. The progress equations are:

```text
progress.completions = count(candidates where state == "completed")
progress.candidatesConsidered = count(candidates where consideredAt != null)
progress.evaluationsConsumed = count(candidates where evaluationConsumed == true)
```

These counters are transactionally maintained authority, while the equalities make the complete candidate array an independent consistency check. Always `evaluationsConsumed <= candidatesConsidered <= attemptBudget`; late completion can increase completions after `finishedAt` but cannot add a candidate or evaluation.

The spend equations are:

```text
committedMicros
  = verifiedCostMicros
  + activeReservationMicros
  + indeterminateReservationMicros

remainingAuthorizedMicros = ceilingMicros - committedMicros
```

The public snapshot omits the internally captured spend-policy version because it is durable authorization evidence rather than operator state; V1's public ceiling remains exactly `1_000_000` micros.

### Resume Run Candidate

```text
ResumeRunCandidate {
  applicationId: string
  applicationLabel: string
  ordinal: integer 0..19
  state:
    | "pending"
    | "evaluating"
    | "recovering"
    | "compensating"
    | "completed"
    | "skipped"
    | "failed"
    | "cancelled"
  stage:
    | "admission"
    | "requirements"
    | "draft"
    | "artifact_recovery"
    | "completion_gate"
    | "compensation"
    | null
  reasonCode: ResumeReasonCode | null
  evaluationConsumed: boolean
  artifactSetId: string | null
  completion: ResumeCompletionSummary | null
  consideredAt: timestamp | null
  updatedAt: timestamp
  terminalAt: timestamp | null
}
```

The candidate reason-presence and transition rules come unchanged from ticket 07. In particular, ordinary `recovering` has no candidate reason because its quarantine reason belongs to the Artifact Set. `completion` is non-null only for `completed`; `terminalAt` is non-null only for `completed`, `skipped`, `failed`, or `cancelled`; and `consideredAt` is the first committed transition beyond `pending`. A quarantine-guard skip sets `consideredAt` without consuming an evaluation.

### Resume Completion Summary

```text
ResumeCompletionSummary {
  sealedAt: timestamp
  resume: { id: string, url: string }
  note: { id: string, url: string }
  pdf: { filename: string, downloadUrl: string }
}
```

The identical object appears on the completed candidate and its Artifact Set. It is published atomically with the Completion seal, has no partial form, and is reconstructed only from freshly verified stable artifact identities. The PDF response uses `Content-Type: application/pdf` and a UTF-8 `Content-Disposition` filename matching the persisted `filename` exactly.

### Resume Artifact Set Snapshot

```text
ResumeArtifactSetSnapshot {
  artifactSetId: string
  runId: string
  applicationId: string
  candidateOrdinal: integer 0..19
  applicationLabel: string
  revision: integer >= 1
  createdAt: timestamp
  updatedAt: timestamp
  disposition:
    | "recoverable"
    | "compensation_required"
    | "sealed"
    | "compensated"
  pendingBoundary:
    | "stage_pdf"
    | "create_resume"
    | "publish_pdf"
    | "create_note"
    | "validate_completion"
    | "attach_relation"
    | "clear_relation"
    | "archive_note"
    | "remove_published_pdf"
    | "archive_resume"
    | "remove_staged_pdf"
    | null
  quarantine: {
    reasonCode: ResumeArtifactQuarantineReason
    enteredAt: timestamp
    lastAssessedAt: timestamp
  } | null
  availableActions: ("reconcile" | "compensate")[]
  activeAction: {
    kind: "reconcile" | "compensate"
    acceptedAt: timestamp
  } | null
  completion: ResumeCompletionSummary | null
}
```

`availableActions` is deterministically ordered `reconcile` then `compensate`, contains no duplicates, and is empty whenever `activeAction` is non-null. `pendingBoundary` is null exactly for terminal `sealed` or `compensated` sets. `attach_relation` remains the pending boundary after dispatch and verified readback until the atomic Completion seal durably records all terminal facts; a pre-seal crash therefore never exposes a boundary-free unsealed set. `completion` is non-null exactly for `sealed`. The current quarantine episode remains present—and therefore remains in the worklist—throughout an active action, including any forward recovery that reconciliation proves safe. At the action's externally idle stable boundary, quarantine and `activeAction` clear together for `sealed` or `compensated`; otherwise `activeAction` clears beside the unchanged or reclassified quarantine.

### Exact reason registry

Ticket 07's registry is the public `ResumeReasonCode` source of truth:

| Use | Approved reasons |
| --- | --- |
| Pre-provider skip | `artifact_quarantine_active`, `application_unavailable`, `application_not_to_apply`, `application_not_analyzed`, `match_score_missing`, `match_score_below_threshold`, `analysis_score_mismatch`, `candidate_source_incomplete`, `independent_resume_exists` |
| Candidate-Scoped failure | `candidate_source_unavailable`, `candidate_became_ineligible`, `candidate_source_changed`, `independent_resume_created`, `insufficient_resume_evidence`, `requirements_context_exceeded`, `draft_context_exceeded`, `requirements_output_exhausted`, `draft_output_exhausted`, `draft_basis_checkpoint_unavailable`, `pdf_render_rejected` |
| Artifact-originated candidate failure or quarantine | `artifact_checkpoint_unavailable`, `artifact_ownership_unproven`, `artifact_content_mismatch`, `artifact_relation_unproven`, `artifact_result_unreconstructable`, `artifact_compensation_unproven` |
| Authorization-blocked run | `provider_authentication_failed`, `provider_balance_insufficient`, `rate_card_unavailable`, `pricing_approval_expired`, `model_not_approved`, `tokenizer_unavailable`, `protocol_overhead_unapproved`, `spend_authority_unavailable`, `generation_envelope_mismatch`, `provider_pricing_anomaly` |
| Shared provider failure | `provider_request_rejected`, `provider_protocol_failure`, `provider_rate_limit_exhausted`, `provider_unavailable_exhausted`, `provider_transport_exhausted`, `provider_recovery_exhausted` |
| Shared workspace, rendering, storage, checkpoint, or execution failure | `workspace_observation_unstable`, `workspace_unavailable`, `workspace_access_invalid`, `workspace_contract_mismatch`, `artifact_rendering_unavailable`, `artifact_storage_unavailable`, `checkpoint_key_unavailable`, `checkpoint_store_unavailable`, `master_checkpoint_unavailable`, `run_store_unavailable`, `storage_failure_unclassified`, `run_execution_failure` |
| Standard terminal reason | `target_met`, `spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `operator_cancelled` |

The six compact `artifact_*` codes belong to `ResumeReasonCode` because ticket 07 permits an applicable definitive artifact-originated cause on a `compensating` or `failed` candidate. They also form the narrower `ResumeArtifactQuarantineReason` union. A quarantine code does not populate the candidate or run reason merely because quarantine exists: ordinary potentially sealable `recovering` keeps its cause only in the Artifact Set, while a candidate uses the code only when it is the definitive cause retained through compensation or terminal failure.

`ResumeRunReadinessReason` is exactly:

```text
"resume_configuration_invalid"
| "run_store_unavailable"
| "checkpoint_key_unavailable"
| "checkpoint_store_unavailable"
| "spend_authority_unavailable"
| "workspace_unavailable"
| "workspace_observation_unstable"
| "workspace_access_invalid"
| "workspace_contract_mismatch"
| "master_resume_unavailable"
| "artifact_rendering_unavailable"
| "artifact_storage_unavailable"
| "generation_envelope_mismatch"
| "rate_card_unavailable"
| "pricing_approval_expired"
| "model_not_approved"
| "tokenizer_unavailable"
| "protocol_overhead_unapproved"
| "provider_authentication_failed"
| "provider_balance_insufficient"
| "provider_pricing_anomaly"
| "provider_acceptance_unproven"
```

Use `resume_configuration_invalid` for definite missing or invalid local settings; the four durable-state/authority codes for the failed transactional, protected-checkpoint, or reservation capability; the four `workspace_*` codes for transport, stable observation, access, or schema/enhanced-Markdown/Artifact-ID conformance; `master_resume_unavailable` when no unique complete Master Resume can be selected; the rendering/storage codes for deterministic PDF or digest-verified Artifact Set storage readiness; the envelope, rate-card, pricing-approval, pricing-anomaly, model, tokenizer, and overhead codes for their exact ticket-03 approval gates; the provider authentication/balance codes for their respective account checks; and `provider_acceptance_unproven` when current sanitized acceptance-probe evidence for either approved stage is absent or failed. Apply ticket 07's deterministic authority order and return the first failing gate. Applicable setting and workspace-schema detail remains in the safe structured `validationFailures` array. `storage_failure_unclassified`, `run_execution_failure`, provider dispatch/recovery exhaustion, and candidate codes are not readiness labels; unexpected start execution defects use sanitized `internal_error`.

### Command and conflict behavior

Start and Artifact Set action idempotency bindings are retained with their resources. An exact replay always returns the resource's current snapshot with the command's original success status, even if background work advanced it. Reusing the key with any different canonical request field returns `idempotency_conflict` and never performs a current-state check. For an Artifact Set action, the current snapshot is observation only: after the accepted action settles, it may no longer depict that action and may eventually depict a later quarantine episode.

For a new start key, an Active Resume Run wins over readiness failure and returns `resume_run_active`. With no active run, readiness is checked before the queue snapshot and atomic creation. Successful readiness with no candidates creates the already-defined zero-candidate `queue_exhausted` run.

For a new Artifact Set action key, an unknown ID returns `not_found`; a stale revision returns `resume_artifact_state_changed`; a current revision with another action active returns `resume_artifact_action_active`; and a current revision whose requested kind is unavailable returns `resume_artifact_action_unavailable`. Each state conflict returns the current safe Artifact Set Snapshot. Matching revision never replaces fresh ownership and evidence checks performed by the accepted action.

### Polling and rediscovery

The API promises stable lookup, revision monotonicity, and non-cacheable current snapshots—not a polling interval. The dashboard can:

1. call active lookup on load to reconnect to ongoing scheduling;
2. call latest lookup to rediscover the most recently created finished run when no run is active;
3. poll a known non-finished run by ID;
4. list unresolved quarantines independently of run age;
5. poll an Artifact Set by ID after accepting an action; and
6. refetch its owning run after the action settles so audited completion is reflected.

No client may infer that `finishedAt` freezes the whole snapshot, that `completions <= target`, or that the absence of an Active Resume Run means there is no unresolved quarantine.

### PDF basename normalization v1

Company and Role come from the admitted Resume Candidate Source Version. User is the valid normalized configuration value captured by the run-creation transaction, so restart or later configuration edits cannot alter naming. For each component:

1. normalize to Unicode NFKC;
2. retain Unicode general categories Letter, Number, and Mark;
3. replace every other maximal run with one hyphen and trim surrounding hyphens;
4. preserve case;
5. truncate to 64 UTF-8 bytes without splitting a code point; and
6. trim any trailing hyphen exposed by truncation.

All components must remain non-empty. Join them with hyphens and append `.pdf`. The resulting maximum is 198 UTF-8 bytes. The Artifact Set transaction persists that exact basename; later source or configuration edits cannot rename it. Storage and verification use Artifact Set identity, never the basename.

### Migration and generated client

FastAPI/Pydantic remains the schema source of truth. The implementation adds named request, snapshot, success, and typed-error models; emits and commits the OpenAPI document; regenerates `@merida/api-client`; and consumes only generated operations and types through the dashboard adapter. No dashboard-local duplicate of the wire contract is permitted.

Internal implementation may be sequenced additively behind a non-public boundary, but the supported contract cutover is one coherent change: enable the durable routes, migrate the dashboard, and remove the synchronous create and Resume-ID download routes plus their OpenAPI paths and generated symbols. The extension is unaffected. Historical legacy artifacts are not adopted into new Artifact Sets, and V1 promises neither a `410 Gone` tombstone nor a compatibility writer.

Removing the Resume-ID PDF route is an intentional read-compatibility contraction, not a dual-writer requirement: legacy PDFs that have no Resume Artifact Set ID cease to have a supported API download URL at cutover and remain unmanaged files outside this contract. V1 does not infer an Artifact Set ID, migrate their index entries, or retain `downloadResumePdf` solely to expose them.

## User Stories

1. As an operator, I want to submit an explicit Resume Batch Target, so that starting work is intentional and independent of the visible queue page.
2. As an operator, I want start acceptance to return a durable snapshot immediately, so that I can leave or reload without holding one generation request open.
3. As an operator, I want an exact start replay to return the original run forever, so that retrying an uncertain response cannot duplicate paid work.
4. As an operator, I want a distinct start rejected while another Resume Run is active, so that two batches cannot compete for the same queue or spend authority.
5. As an operator, I want failed readiness rejected before run creation, so that an accepted run always has the durable authority needed to begin safely.
6. As an operator, I want an empty eligible queue represented by an idempotent finished run, so that replay cannot unexpectedly consume Applications added later.
7. As an operator, I want active, latest, and by-ID lookup, so that reload can reconnect without turning V1 into a full history browser.
8. As an operator, I want cancellation to acknowledge the committed scheduling barrier while safe drain continues, so that HTTP success is not mistaken for rollback or immediate completion.
9. As an operator, I want lifecycle, stopping outcome, and reason shown independently, so that I can distinguish why scheduling stopped from whether settlement and artifact drain are finished.
10. As an operator, I want the whole fixed Candidate Set and independent progress counters, so that skips, evaluations, backfill, and late completion remain understandable.
11. As an operator, I want exact Committed Spend constituents in integer micros, so that uncertain reservations are visible without being mislabeled as an invoice.
12. As an operator, I want each candidate's safe stage, state, reason, and timestamps, so that I can diagnose progress without seeing prompts, model attempts, or private source.
13. As an operator, I want completed Resume, Note, and PDF links published as one atomic summary, so that no partial response can masquerade as a Resume Completion.
14. As an operator, I want a human PDF filename containing Company, Role, and User, so that downloads remain recognizable while Artifact Set identity prevents collisions and adoption.
15. As an operator, I want every unresolved Resume Artifact Quarantine in an independent worklist, so that attention survives run completion and later unrelated runs.
16. As an operator, I want a stable Artifact Set page after quarantine clears, so that an accepted action never causes the resource I am polling to disappear.
17. As an operator, I want reconciliation and compensation presented as distinct available actions, so that inspection cannot silently become deletion authority.
18. As an operator, I want stale revisions and competing actions rejected with the current safe snapshot, so that I can review changed evidence before acting again.
19. As an operator, I want an accepted Artifact Set action to survive restart, so that browser lifetime does not control recovery or cleanup.
20. As an operator, I want late audited completion to update truthful results without rewriting the run's stopping outcome, so that historical cause and later proof are both preserved.
21. As an operator, I want known runs, Artifact Sets, and idempotency bindings retained in V1, so that delayed follow-up does not silently become an unknown resource.
22. As an operator, I want a missing or changed historical PDF to fail closed at download without reopening the sealed Completion, so that drift is visible but cannot trigger unsafe same-run repair.
23. As a frontend developer, I want named OpenAPI operations and closed generated unions, so that the dashboard cannot invent a second interpretation of the state machine.
24. As a maintainer, I want the synchronous writer removed at the durable cutover, so that all Resume mutations pass through one transaction and recovery authority.
25. As a maintainer, I want a strict public allowlist and privacy tests, so that future diagnostics cannot leak source, provider, checkpoint, or filesystem content.
26. As an operator, I want reuse of a start idempotency key with another target rejected and a distinct active-run conflict to identify the active run, so that request identity cannot change and another dashboard session can reconnect safely.
27. As an operator, I want a not-ready start to report one bounded readiness reason with only applicable safe configuration or workspace-schema validation detail, so that I can remediate the failed capability without seeing private evidence or raw integration errors.
28. As an operator, I want an exact reconciliation or compensation replay to return the Artifact Set's current snapshot without starting the action twice, so that an uncertain command response remains safe even after the resource advances or enters a later quarantine episode.
29. As an operator, I want reuse of an Artifact Set action key for another set, action, expected revision, or canonical request rejected, so that historical authorization cannot be redirected toward a different mutation.
30. As an operator, I want Artifact Set disposition, quarantine reason, and earliest unverified boundary reported independently, so that I can distinguish forward recovery, required compensation, and uncertainty without treating intent or dispatch as success.
31. As an operator, I want only currently evidence-safe Artifact Set actions exposed and an unavailable action rejected explicitly, so that generic retry or acknowledgement cannot become mutation authority.
32. As an operator, I want an accepted Artifact Set action to keep its Application quarantined until an externally idle safe boundary while unrelated Resume Runs may proceed, so that original mutation and new evaluation never overlap unnecessarily.
33. As an operator, I want cancellation of a known run to be intrinsically repeatable and return its current snapshot without rewriting an earlier stopping decision, so that retrying the command remains safe after drain or finish.
34. As an operator, I want a sealed PDF referenced by a retained Completion Summary to avoid automatic time pruning and public deletion, so that a durable completion does not advertise an intentionally expired download.
35. As a maintainer, I want cutover to remove both the synchronous writer and Resume-ID PDF route without adopting legacy files or promising a `410` adapter, so that the breaking read/write boundary is explicit rather than accidental.

## Implementation Decisions

### Public schema ownership

- Define the Resume Run, candidate, progress, spend, Completion Summary, Artifact Set, quarantine, action, request, response, and typed error models in the Resumes public-schema module using `ApiModel` so unknown JSON fields remain forbidden and camel-case aliases are generated consistently.
- Represent every enum as a closed `Literal` union. Reuse one named `ResumeCompletionSummary` in both candidate and Artifact Set schemas and one named `ResumeArtifactSetSnapshot` in by-ID, action, and worklist responses.
- Define `ResumeRunReadinessReason` as its own closed union with one deterministic gate-to-reason mapper. Attach only the safe setting and workspace-schema failures permitted by `CommonResponse`; reject free-form readiness labels.
- Use strict integers for `target` and `expectedRevision`: reject booleans, floats, numeric strings, missing values, and unknown fields. Apply the exact shared idempotency-key grammar at both command boundaries.
- Serialize timestamps as timezone-aware RFC 3339 UTC values. Never derive revision from time; revision is a persisted monotonic integer advanced in the same transaction as the state or evidence change it represents.
- Keep run and Artifact Set projections content-free. Use an explicit serialization allowlist rather than serializing durable store rows or domain objects wholesale.

### Run commands and lookup

- Parse and validate the request and idempotency-key syntax before command dispatch. Resolve an existing binding before active/readiness checks, and compare the complete canonical request (`target`) rather than only its route and key.
- Acquire the Active Resume Run claim, capture the fixed Candidate Set and Master checkpoint, establish the run and idempotency binding, and return the first revision through one run-creation transaction. Wake execution only after commit.
- When readiness succeeds with no eligible candidate, use that same transaction to create and bind an immediately finished zero-candidate `queue_exhausted` run. Report the fixed ceiling and full remaining authorization while every progress and spend constituent other than the ceiling and remaining authorization is zero.
- Implement active lookup from the single scheduling claim and latest lookup from immutable creation sequence. Never select latest by `updatedAt` or revision.
- Commit cancellation before returning. Return a known run's current snapshot for every repeat and never synthesize a cancellation result from worker state.
- Increment run revision for each public state mutation and for a hidden durable mutation whose changed safety evidence matters to later observation. Keep the first outcome/reason/stopping time immutable even when other fields advance.

### Worklist and Artifact Set actions

- Build the worklist from current unresolved quarantine episodes, not from run lifecycle or candidate reasons. Use the tuple `(enteredAt, artifactSetId)` as the opaque ordering position; a new quarantine episode receives a new `enteredAt`.
- Return full Artifact Set Snapshots so worklist and by-ID representations cannot drift. Use a named worklist pagination model with its 1-through-50 bound rather than changing the existing queue pagination schema. Do not add a second quarantine-entry state model or a total count that becomes stale during pagination.
- Persist each action idempotency binding and `activeAction` in the Resumes transaction authority before returning `202`. Wake the artifact worker only after commit and retain the slot across lease loss or process restart.
- Bind every Artifact Set action key to the Artifact Set, action kind, canonical request including expected revision, accepted revision, and acceptance time. Resolve that binding before revision and availability checks; an exact replay returns the original success status and current snapshot without waking work again.
- Keep the current quarantine episode and `activeAction` discoverable while the accepted action freshly assesses evidence and performs any resulting forward recovery or compensation. Clear `activeAction` only at an externally idle stable boundary: sealed completion, verified compensation, or an unchanged/reclassified quarantine with automatic mutation stopped. Recompute `availableActions` from that state.
- Enforce revision, action availability, fresh evidence, exact ownership, and disposition independently. Optimistic concurrency grants no mutation authority.

### PDF storage and download

- Capture the valid normalized configured User value in the run-creation transaction. Persist basename-normalization version 1 and the exact basename derived from that captured value and the admitted Candidate Source in the Artifact Set transaction, so restart or later configuration edits cannot rename the artifact.
- Index the published PDF primarily by Artifact Set ID and bind it to the Resume document and PDF byte digests from ticket 05.
- Before download, resolve only the exact Artifact Set entry, ensure the indexed name cannot escape the configured store, and verify the bytes. Never fall back to Resume ID, title, filename search, or legacy-file adoption.
- Serve the persisted basename with UTF-8 `Content-Disposition`. Return sanitized `pdf_not_found` for every unknown or currently unverified download target without mutating a sealed Completion.

### Polling and caching

- Apply `Cache-Control: no-store` to current run, Artifact Set, worklist, command, typed-error JSON, and verified PDF download responses. V1 does not require ETags, conditional requests, event streams, or server-selected polling intervals.
- Serve ordinary run, Artifact Set, and worklist reads only from durable coordination state and keep them side-effect free. Do not perform live workspace or PDF validation during those reads; reserve exact path and digest verification for PDF download.
- Treat revision as change detection, not as proof that a worker is alive. Leases, deadlines, attempts, and heartbeats remain private.
- Let ticket 09 choose polling cadence and visual behavior while preserving active/latest/by-ID rediscovery and the separate quarantine worklist.

### Idempotency, typed errors, and retention

- Persist start bindings with the canonical target and Artifact Set action bindings with their complete accepted intent. Resolve an existing binding before mutable-state checks; exact replay retains the command's original success status, returns the resource's current snapshot, never reacquires authority, and never wakes work twice.
- Persist the documented validation and conflict precedence inside the command service and transaction authority rather than relying only on route-handler order. Invalid, not-ready, stale, active, and unavailable commands create no new idempotency binding or mutation.
- Define named typed error responses for readiness, active-run, idempotency, Artifact Set state, temporary coordination, resource-not-found, PDF-not-found, and unexpected-failure cases. Expose only the bounded safe sibling fields documented by this contract.
- Retain Resume Run Snapshots and their bounded Candidate Sets and results, Resume Artifact Set Snapshots and non-reused identities, start and action idempotency bindings, and sealed digest-verified PDFs without an automatic V1 TTL. Keep private checkpoint retirement separate; any public pruning policy requires a later contract migration.

### OpenAPI, generated client, and cutover

- Add every route and operation ID from the route table to FastAPI, emit OpenAPI, commit the regenerated document and `@merida/api-client`, and use those generated functions through the dashboard's existing API adapter.
- Extend the shared typed error model only with the bounded codes and optional safe fields required here: `reasonCode`, `activeRunId`, and sibling current `artifactSet` where specified. Do not put polymorphic snapshots inside a free-form error detail.
- Update the public-operation allowlist, route documentation, workflows, architecture/operations guidance, and Resumes context links in the same implementation stream.
- Perform one supported cutover with no dual writer. Switch the public route allowlist, OpenAPI, generated client, and dashboard together; remove the two legacy paths and all generated `CreateResume*` and `DownloadResumePdf*` exports; and leave the extension unchanged. The removed routes become ordinary `404` paths with no `410`, hidden fallback, legacy-index migration, or workspace mutation.

## Testing Decisions

### Primary acceptance seam

- Exercise the composed public API against a durable deterministic Resume Run worker and reopen a fresh app instance over the same state. Assert that every accepted command survives restart and every response can be reconstructed without an in-memory task or cached provider/artifact response.
- Treat public HTTP responses, reconstructed durable snapshots, and observed provider/workspace/PDF effects as the behavior under test; do not assert worker-loop implementation detail, lease timing, or private record layout.
- Use the existing Application Analysis public Run API, idempotency, cancellation, fresh-app restart, OpenAPI inventory, and emitted-client equality tests as the primary prior art. Reuse ticket 05's artifact effect and crash matrices below this seam rather than reproducing every effect permutation through HTTP.
- Anchor acceptance with two vertical restart scenarios: start, restart, reconnect, finish, replay, and download; and quarantine, release the owning run claim, restart, reconcile or compensate, restart mid-action, settle or re-quarantine, and replay.
- Keep live provider and live Notion traffic out of routine tests. Use deterministic adapters and recorded conformance fixtures; sanitized live probes remain operational readiness evidence.

### OpenAPI and generated-client contract

- Assert the exact method, path, operation ID, status, request body, header, response model, and typed error set for the ten new or replacement routes, plus continued compatibility of the existing Resume Creation Queue route.
- Assert that emitted OpenAPI equals the committed client input, generation is clean, every enum is closed, timestamps and integer bounds are present, and unknown request fields are forbidden.
- Typecheck the dashboard against only generated operations and types. Assert the old routes, OpenAPI paths, SDK functions, and `CreateResume*`/`DownloadResumePdf*` types are absent after cutover.

### Start, lookup, and cancellation matrices

- Cover missing/malformed keys, missing/nonintegral/out-of-range target, extra `limit`, exact replay before and after finish, same-key/different-target conflict, distinct-key active conflict, each bounded readiness rejection, and successful empty-queue creation.
- Reject coerced scalar forms including booleans, numeric strings, and integral floats. Prove that an invalid or not-ready command did not bind its idempotency key by reusing that key in a later valid command.
- Prove conflict precedence: exact replay before active/readiness, Active Resume Run before readiness for a fresh key, and no idempotency binding on invalid or not-ready requests.
- Cover active `run: null`, latest `run: null`, active versus most-recently-created selection, known older by-ID lookup, unknown IDs, queued cancellation, running cancellation, repeat cancellation, cancellation after a prior stopping decision, and cancellation of a finished run.
- Replay an older finished start while a newer run is active, then advance the older run through audited completion or spend settlement and prove immutable creation order still keeps the newer run at `latest`.
- Assert cancellation rejects every supplied body and still performs no state change for malformed requests.

### Snapshot invariants

- Assert the complete fixed candidate array, zero-based immutable ordinals, `attemptBudget === candidates.length`, and the exact progress semantics for ordinary Admission and the quarantine-guard exception.
- Cover every lifecycle/outcome/state/stage enum and every ticket-07 reason code with its reason-presence rule. Assert that outcome, reason, and stopping time become non-null together and never change during drain or late recovery.
- Assert spend equations at zero, exact ceiling, one micro below/above authorization, active reservation, indeterminate reservation, trustworthy later settlement, and post-finish revision changes.
- Cover a finished run gaining a late Completion, meeting or exceeding target without outcome rewrite, and retaining a recovering candidate while another run becomes active.
- Apply a public serialization denylist for Job Content, Master Resume content, Application Analysis, prompts, model/provider details, raw errors, calls and attempts, source proofs, digests, checkpoints, leases, worker IDs, transient URLs, and filesystem paths.

### Artifact Set and quarantine matrices

- Cover every disposition, pending boundary, quarantine reason, available-action combination, active action, and terminal nullability invariant.
- Cover exact action replay after revision advance and after settlement; same-key/different-request conflict; stale revision; already active action; unavailable action; unknown ID; and both accepted actions across process restart.
- Cover missing and malformed action keys; missing, boolean, string, float, zero, and extra-field `expectedRevision` requests; and prove every rejected request leaves the key reusable for a later valid action.
- Assert that worklist ordering and opaque pagination remain deterministic while an earlier item resolves, an active action remains unresolved, and a later new quarantine episode enters. Ensure the by-ID resource survives removal from the worklist.
- Prove an unresolved or actively resolving Artifact Set permits a run for unrelated Applications while excluding its own Application at queue snapshot and pre-admission guard until seal, compensation, or safely re-quarantined idle settlement.
- Run ticket 05's effect, ambiguous-response, compensation, quarantine, and seal crash matrices through the public projection. Assert `pendingBoundary` advances only after fresh verification and never from intent or dispatch alone.
- Assert that action acceptance and Artifact Set revision/active-action state commit atomically, and that a late seal updates Artifact Set, candidate Completion Summary, run progress, and both revisions without duplicate counting.

### Completion, PDF, and drift

- Prove that no partial Resume, Note, or PDF reference appears before the seal and that candidate and Artifact Set Completion Summaries are byte-for-byte equal afterward.
- Publish golden filename vectors for ASCII punctuation, whitespace runs, NFKC compatibility characters, composed/decomposed Unicode, combining marks, emoji/separators, empty components, multibyte truncation, trailing-hyphen trimming, repeated companies/roles, and the 198-byte maximum.
- Assert the download's media type, UTF-8 persisted basename, Artifact-Set-keyed lookup, path containment, byte-digest validation, and safe 404 behavior for unknown, unsealed, missing, modified, or legacy-only PDFs.
- Mutate every sealed external artifact and relation through ticket 05's drift tests. Ordinary snapshot reads remain content-free and side-effect free; PDF drift fails closed; Completion, candidate state, run progress, and future-run exclusion remain unchanged.
- Assert `Cache-Control: no-store` on every dynamic JSON success, typed error, and verified PDF response.
- Make coordination unavailable before a new command can commit and assert sanitized `503 resume_coordination_unavailable` with no binding or mutation. Separately interrupt execution after acceptance, recreate the app over the same durable state, and prove the accepted run or Artifact Set action resumes without a fabricated revision or transition.
- At the coordinated cutover, call both removed legacy paths and prove ordinary `404` behavior; posting to the former writer must create no workspace artifact, PDF, or durable Resume Run state.

## Out of Scope

- Implementing the durable Resume Run product in this decision ticket.
- Dashboard layout, wording, cadence, animations, notification behavior, and interaction details owned by ticket 09.
- Full Resume Run history browsing, search, deletion, archival, or time-based presentation pruning.
- WebSockets, server-sent events, webhooks, long polling, ETags, conditional GET, or a separate action-job resource.
- Action cancellation, percentage progress, worker/lease diagnostics, generic retry, acknowledgement, force completion, force cleanup, or force deletion.
- Historical Artifact Drift monitoring, snapshot diagnostics, repair, replacement, retirement, or renewed eligibility.
- Adoption or migration of legacy or independently existing Resumes, Notes, PDFs, relations, or filenames into a Resume Artifact Set.
- A `410 Gone` compatibility endpoint, a second public Resume writer, or permanent support for the synchronous creation contract.
- Continued API download access for legacy Resume-ID-indexed PDFs after the Artifact Set cutover.
- Changing the Resume Generation Envelope, two-attempt stage limits, $1.00 Resume Run Spend Ceiling, conservative settlement, Candidate Set, source consistency, failure scope, cancellation, artifact recovery, compensation, quarantine, or Completion-seal decisions from tickets 01–07.
- Changing Application Analysis behavior, public contracts, generated-client operations, or concurrency with Resume Runs.
- Exposing prompts, model reasoning, provider payloads, canonical Resume or Note content, Job Content, Master Resume content, source proofs, checkpoint material, ownership evidence, digests, filesystem paths, or raw integration errors.
- Physical database layout, worker scheduling/backoff, key-provider selection, deployment-secret delivery, backup retention, or live migration mechanics.

## Further Notes

- The dashboard may prefill target `5`, but the API never defaults it. Target `1` replaces the former per-row single-Resume mutation.
- “Finished” means safe drain completed, not that every field is permanently frozen. The stopping decision is immutable; audited completion and trustworthy spend facts may still advance revision.
- A sealed Resume Completion remains historical truth if its external artifacts later drift. The download route fails closed rather than turning a historical problem into same-run mutation authority.
- The Application Analysis API is useful prior art for `202` start, stable lookup, cancellation, CommonResponse envelopes, OpenAPI generation, and dashboard polling. Resume-specific candidate, spend, artifact, quarantine, retention, and late-completion semantics are not shared schemas.
- [ADR 0003](../../../apps/api/merida_api/features/resumes/docs/adr/0003-expose-durable-resume-operations-through-the-dashboard-api.md) records the compatibility commitment and its operator-facing consequences. ADRs 0001 and 0002 continue to own Artifact Set identity/recovery and audited late completion respectively.
- This document is the published `to-spec` synthesis of the completed grill. Its primary acceptance seam is the composed public API reopened over the same durable state, and its triage status remains `ready-for-agent`; implementation must not reopen settled tickets 01–07 through local schema or dashboard choices.
