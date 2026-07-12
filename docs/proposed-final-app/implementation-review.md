# Proposed App Implementation Review

## Outcome

The proposed app has a coherent product shape and manageable module seams. The original document set was not implementation-ready as a whole: issues 05 through 10 were still open, `routes.md` had no locked namespace, and older docs still referenced Quick Capture, streamed Analysis, separate `/analysis` and `/resumes` pages, and one broad Workspace interface.

The implemented vertical slice resolves the runtime ambiguity without changing the accepted product contract:

- `/dashboard` is the single React LLM process console.
- the React Chrome side panel owns review-first Capture.
- Notion remains the record-management surface.
- FastAPI routes are thin adapters under `/api/v1`.
- `ApplicationCapture`, `ApplicationAnalysis`, and `ResumeCreation` remain the public workflow interfaces.
- each workflow receives only its narrow store interface.
- Notion and test-only fake adapters sit behind those workflow-owned seams.
- queues are eligible-only and cursor values are opaque.
- Application Analysis is bounded and returns one final result.
- Resume Creation is one-at-a-time and idempotent.

## Implemented Repository Shape

```text
apps/api/
  merida_api/
    core/                  settings and Capture auth
    features/
      applications/       Capture and Analysis modules
      job_postings/       source parsing and URL canonicalization
      resumes/            Resume Creation module
    integrations/         Notion and PDF adapters
    shared/               opaque pagination
  tests/                  public REST tests and injected boundary fakes
apps/web/                  functional React dashboard
apps/extension/            functional React MV3 side panel
app-data/                  generated PDFs and recovery metadata
```

The existing `src/` Node prototype and `apps/*-prototype/` visual studies remain runnable references. They are not imported by the new FastAPI or React implementation.

## Public Contracts

The implemented HTTP namespace is `/api/v1`.

| Method | Path | Owner |
| --- | --- | --- |
| `GET` | `/api/v1/health` | app readiness |
| `GET` | `/api/v1/operator/settings` | safe read-only settings |
| `POST` | `/api/v1/applications/prepare` | Application Capture |
| `POST` | `/api/v1/applications/confirm` | Application Capture |
| `GET` | `/api/v1/applications/analysis/queue` | Application Analysis |
| `POST` | `/api/v1/applications/analysis/run` | Application Analysis |
| `GET` | `/api/v1/resumes/queue` | Resume Creation |
| `POST` | `/api/v1/resumes/create` | Resume Creation |
| `GET` | `/api/v1/resumes/{resume_id}/pdf` | Resume artifacts |

Quick Capture is not in v1. There is no `/applications/capture` route and no streaming Analysis transport.

## Credential-Free Acceptance

The product has no demo mode, fixture workspace, reset route, or runtime adapter selector. Credential-free tests inject deterministic boundary fakes into the application factory and exercise the same workflow modules, routers, request validation, React clients, queue rules, and PDF contract without private Notion or DeepSeek credentials. Test state is isolated under temporary test roots and is never presented as product data.

## Verification

- FastAPI public-contract tests cover readiness, secret-safe settings, Capture auth, prepare/confirm, duplicate Capture, opaque pagination, Analysis queue movement, idempotent Resume Creation, PDF links, invalid cursors, and built dashboard serving.
- dashboard-session tests cover batch clamping, queue reset, and retained artifact links.
- Capture-session tests cover in-memory Job Content, preserved edits after failure, and dirty-review discard protection.
- production builds complete for the React dashboard and MV3 extension.
- live FastAPI checks confirm health, dashboard serving, eligible queue data, and all named OpenAPI operations.

## Remaining Real-Runtime Cutover

The FastAPI app always composes the real Notion workspace and reports blocked readiness when required configuration or DeepSeek workflow adapters are incomplete. It never falls back to deterministic product behavior. This is intentional: the existing Node implementation contains substantial evidence validation, compensation, and generation behavior that must be ported without weakening guardrails.

The remaining migration should proceed in vertical slices:

1. implement Notion conformance for `CaptureStore`, then cut over real Capture;
2. implement `ApplicationAnalysisStore` plus the DeepSeek Analysis model adapter and parity fixtures, then cut over Analysis;
3. port Matching, evidence validation, Resume Draft generation, Notes rendering, and artifact compensation behind `ResumeCreationStore`, then cut over Resume Creation;
4. run the versioned parity corpus against each real adapter before removing the Node route for that workflow;
5. declare the single real runtime complete only when all readiness checks and cleanup fixtures pass.

This keeps the application manageable: each workflow can be migrated and verified independently while the prototype remains the executable reference.
