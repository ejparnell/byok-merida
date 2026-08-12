# Architecture

Merida is a local-first application with one FastAPI backend and two React clients: the operator dashboard and the Chrome side-panel extension. Notion is the durable record-management surface. DeepSeek supplies structured model output, and the backend owns all provider credentials and workflow policy.

## Runtime shape

```text
Chrome job page
  -> React side-panel extension
    -> FastAPI /api/v1 capture routes

React /dashboard
  -> FastAPI /api/v1 analysis, resume, readiness, and recovery routes

FastAPI
  -> Applications: Capture and Analysis orchestration
  -> Job Postings: source parsing and URL canonicalization
  -> Resumes: evidence gating, generation, rendering, and artifact commit
  -> Matching: deterministic scoring and evidence matching
  -> workflow-owned store and model interfaces
    <- Notion, DeepSeek, PDF, and filesystem adapters

Notion
  -> Applications, Resumes, and Resume Fit Analysis Notes

app-data/
  -> export/ generated PDFs
  -> recovery/ incomplete-effect journal and Analysis Run SQLite store
```

## Technology stack

| Area              | Technology             | Responsibility                                                                                          |
| ----------------- | ---------------------- | ------------------------------------------------------------------------------------------------------- |
| Backend           | FastAPI + Pydantic     | HTTP routing, validation, auth, OpenAPI, workflow composition, and health checks.                       |
| Backend tests     | pytest                 | Domain, route, adapter, recovery, and public-contract verification.                                     |
| Dashboard         | React + TypeScript     | Compact process console for readiness, durable Analysis Runs, Resume Creation, and Notion review links. |
| Extension         | Chrome MV3 + React     | Active-page evidence collection, parsed-field review, and confirmed Capture writes.                     |
| Frontend build    | Vite                   | Dashboard and independently loadable extension builds.                                                  |
| API client        | Generated from OpenAPI | Typed calls from both React clients to FastAPI.                                                         |
| Durable workspace | Notion                 | Existing Applications, Resumes, and Notes databases.                                                    |
| Run coordination  | SQLite                 | Content-free Analysis Run identity, progress, leases, call reservations, and restart recovery.          |
| Model provider    | DeepSeek               | Application Analysis, fit-requirement extraction, and resume generation.                                |
| Matching          | Python                 | Provider-independent normalization, evidence matching, and versioned scoring.                           |
| PDF export        | Python backend adapter | Generates application-ready PDFs from the validated resume document.                                    |

## Ownership and seams

Routes and screens are adapters; workflow rules live in feature modules behind narrow interfaces.

| Owner                     | Public seam                                                                                       | Hides                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Application Capture       | `prepare(evidence)`, `confirm(draft)`                                                             | Parsing, duplicate detection, validation, and Notion writes.                                                  |
| Application Analysis      | `get_queue(query)`, `start_run(target, key)`, `get_run(id)`, `get_active_run()`, `cancel_run(id)` | Fixed Candidate Sets, sequential evaluation, model repair, spend enforcement, durable progress, and recovery. |
| Resume Creation           | `get_queue(query)`, `create(application_id)`                                                      | Evidence gates, model calls, claim repair, document rendering, and compensation.                              |
| Matching                  | `match(targets, evidence_items, scoring_policy)`                                                  | Normalization and deterministic scoring details.                                                              |
| Resume Artifact Committer | `commit(application, bundle, staged_pdf)`                                                         | Ordered Notion/PDF effects, relations, rollback, and recovery reporting.                                      |
| Extension evidence        | `collectCaptureEvidence()`                                                                        | Chrome tab/frame reads and bounded in-memory page content.                                                    |
| Extension session         | `prepare`, `updateReview`, `confirm`, `clear`                                                     | Review state, dirty-discard protection, and confirmation state.                                               |
| Dashboard session         | queue/start/follow/cancel/create actions                                                          | Pending state, cursors, Analysis Run polling, retained terminal results, and operator-facing errors.          |

There is no global workspace or model interface. Capture, Analysis, and Resume Creation each own the smallest protocol they need. The production Notion and DeepSeek adapters may implement several protocols, while the composition root passes each workflow only its owned seam. Tests inject deterministic fakes through the same interfaces.

Notes are not a standalone feature module or editor. Resume Creation owns the Resume Fit Analysis document behavior and persists that document through its workspace interface into the existing Notion Notes database.

## Data and storage

Notion is the only durable product workspace. The compatibility adapter translates canonical domain names to the existing physical Applications, Resumes, and Notes schemas and validates them before writes. Record editing and management remain in Notion.

The backend also writes three supported local artifact classes:

- generated PDFs and their hidden resume-ID lookup metadata under `app-data/export/`;
- incomplete-effect recovery entries under `app-data/recovery/effects.json`;
- content-free Analysis Run coordination metadata under `app-data/recovery/analysis-runs.sqlite3`.

The Analysis Run Store is owned by the Applications context. It contains run and
idempotency identities, the fixed ordered Candidate Set, lifecycle and outcome,
safe candidate states, leases, provider-call state, and integer-micro spend
reservations. It does not duplicate Job Content, prompts, provider payloads,
generated analysis, or model reasoning. Notion remains authoritative for each
Application and completed analysis.

Job content and Master Resume content are processed in memory and at provider boundaries required by the workflows. Browser clients receive only safe Analysis Run metadata, never Notion tokens, database IDs, DeepSeek keys, prompts, filesystem paths, recovery payloads, Job Content, generated analysis, or model reasoning.

## Analysis Run execution boundary

`POST /api/v1/applications/analysis/run` durably creates one Analysis Run and
returns `202` before provider work finishes. A retained backend worker processes
the fixed Candidate Set sequentially, with one provider call in flight. The
worker reclaims queued runs plus running or cancelling runs with expired leases
after restart; finished runs—including runs with the `cancelled` outcome—do not
resume.

Every provider transmission is admitted by the backend Spend Enforcement
Authority. A complete worst-case reservation must commit transactionally before
dispatch, and the sum of verified cost, active reservations, and indeterminate
reservations—the run's Committed Spend—cannot exceed 500,000 USD micros. Each
Application has one shared budget of three actual transmissions across initial
generation, transport recovery, and structured-output repair.

## HTTP and trust boundary

FastAPI and Pydantic are the source of truth for the public contract. Committed OpenAPI generates `packages/api-client`; `npm run check:generated` fails when the schema and generated TypeScript drift.

| Caller               | Policy                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------- |
| Dashboard            | Same-origin local requests to the FastAPI process; intentional Analysis starts carry `Idempotency-Key`. |
| Chrome extension     | Allowed extension origin plus `X-Capture-Token` on Capture operations.                                  |
| CLI/operator tooling | Backend environment settings; protected write routes require the capture token where documented.        |

FastAPI dependencies own token validation, allowed-origin checks, and settings access. Provider-safe error normalization prevents secrets, raw provider payloads, and local paths from crossing into public responses or logs.

## Verification boundary

`npm test` is the credential-free final-app gate. It verifies generated-client freshness, TypeScript type checking, lint/format, browser-session tests, the full Python suite, production builds, no-demo scans, and the final-only repository guard.

Test fakes live under `apps/api/tests/fakes/`, write only to temporary state, and enter through explicit dependency injection. They are verification adapters, not a second runtime or operator mode.
