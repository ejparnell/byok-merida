# Workflows

Merida has three separate workflows behind three public module interfaces. The React dashboard and extension are adapters over those modules; Notion remains the record-management surface.

## 1. Application Capture

Surface: React Chrome MV3 side panel.

Module interface:

```python
ApplicationCapture.prepare(evidence)
ApplicationCapture.confirm(draft)
```

Flow:

1. The extension verifies its backend URL and Capture token.
2. **Fill Form** collects normalized Capture Evidence from the active tab.
3. `POST /api/v1/applications/prepare` canonicalizes the URL and returns safe review fields without writing.
4. The operator reviews Company Name, Role, optional Location, Job URL, and a readable Job Content preview.
5. **Create in Notion** calls `POST /api/v1/applications/confirm` with reviewed values and the in-memory Job Content.
6. The backend returns `created`, `already_captured`, `needs_review`, or a safe blocked/failed result.

Capture creates an Application with `Application Status = To Apply`, `Analyzed = false`, and no Match Score. Quick Capture is outside v1. Full Job Content is never persisted by the extension.

## 2. Application Analysis

Surface: Application Analysis section on React `/dashboard`.

Module interface:

```python
ApplicationAnalysis.get_queue(query)
AnalysisRunService.start(target, idempotency_key)
AnalysisRunService.active()
AnalysisRunService.get(run_id)
AnalysisRunService.cancel(run_id)
```

Eligibility:

- `Application Status = To Apply`
- `Analyzed = false`
- readable Job Content

Flow:

1. `GET /api/v1/applications/analysis/queue?limit=5` returns an eligible-only preview, total count, and opaque cursor.
2. The operator chooses an **Analysis Batch Target** from 1 through 10. The target is the number of successful Analysis Completions to pursue, not the number of Applications to attempt.
3. The dashboard generates one idempotency key and calls `POST /api/v1/applications/analysis/run` with `{ "target": 5 }` plus `Idempotency-Key`. The preview pagination `limit` remains independent of the start request.
4. The backend durably snapshots the first `min(eligible queue size, target × 2)` Application identities in canonical queue order and returns `202` with the Analysis Run before provider work finishes.
5. A background worker processes that fixed Candidate Set sequentially. It reloads and revalidates each Application immediately before use, backfills after skips and Candidate-Scoped Failures, and evaluates each candidate at most once.
6. A readable existing analysis with incomplete properties is repaired without a provider call and counts as a completion. New analysis keeps DeepSeek thinking at high effort, allows at most 8,000 reasoning-inclusive generated tokens per call, and shares three actual transmissions across initial generation and every recovery path.
7. Before each transmission, the backend transactionally reserves the complete worst-case cost. Committed Spend—verified cost plus active and indeterminate reservations—never exceeds the run's fixed 500,000-micro ($0.50) ceiling.
8. The backend validates the three-sentence summary and three-to-ten evidence-backed signals, calculates Match Score deterministically, writes the body first, then commits final properties. Only that complete boundary increments progress.
9. The worker stops immediately at the target or records one terminal outcome: `target_met`, `spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `cancelled`, `authorization_blocked`, or `failed`.
10. The dashboard polls `GET /api/v1/applications/analysis/runs/{runId}`, reconnects through `/runs/active` after reload, and keeps the terminal result visible. Reaching a terminal state refreshes both queues so completed Applications can move into Resume Creation.

An identical `Idempotency-Key` and target returns the original run. Reusing the
key for another target conflicts, and a distinct start while a run is active
returns that active run's identity without queuing or changing work. Cancellation
stops future provider calls but does not promise to interrupt or refund a call
already in flight; a valid in-flight result is still committed, while an
unreconcilable sent call remains conservatively committed as indeterminate.

Analysis Run coordination lives in the Applications-owned SQLite store, while
Notion remains authoritative for Applications and completed analyses. Backend
startup reclaims queued runs plus expired-lease running or cancelling work,
reconciles uncertain calls before new dispatch, and never restarts a terminal
run.

## 3. Resume Creation

Surface: Resume Creation section on React `/dashboard`.

Module interface:

```python
ResumeCreation.get_queue(query)
ResumeCreation.create(application_id)
```

Eligibility:

- `Application Status = To Apply`
- `Analyzed = true`
- no existing Resume Attachment
- readable Company Name, Role, Job Content, and Application Analysis

Flow:

1. `GET /api/v1/resumes/queue?limit=5` returns an eligible-only, Match Score-ordered queue.
2. The operator selects **Create Resume** on one Application.
3. `POST /api/v1/resumes/create` revalidates eligibility and returns `already_created` when the completion relation exists.
4. The workflow loads Master Resume evidence, extracts Fit Requirements, runs deterministic Matching, and blocks before writes when evidence is insufficient.
5. A validated Resume Document and Resume Fit Analysis are produced from evidence-backed claims.
6. The artifact committer creates the Resume, PDF, and Note, then attaches the final Application relation last.
7. Partial failures are compensated in reverse order and cleanup results are explicit.
8. The dashboard refreshes the queue but retains Resume, Note, and PDF output links.

## Runtime And Test Composition

The final app has one runtime composition: Notion, DeepSeek, PDF, and recovery adapters behind the workflow-owned interfaces. Missing real configuration produces blocked readiness and never falls back to fictional data.

Credential-free tests inject deterministic stores, models, PDF storage, and journals through the application factory. These fakes exercise the same ASGI routes and workflow interfaces but are not selectable by users, persisted as product state, or exposed through OpenAPI.
