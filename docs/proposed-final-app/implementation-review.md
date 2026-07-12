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
| `GET` | `/api/v1/health/notion` | Notion database readiness |
| `GET` | `/api/v1/health/analysis` | Application Analysis readiness |
| `GET` | `/api/v1/health/resumes` | Resume Creation readiness |
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

## Current Real-Runtime Status

The FastAPI app always composes the real Notion workspace. When DeepSeek is configured, it composes task-specific Application Analysis and Resume Creation adapters. Resume Creation now extracts Fit Requirements, validates Job Content evidence, applies versioned deterministic Matching, blocks unsupported generation, validates role-owned claim traces, preserves Master Resume chronology and non-work sections, and renders Notion and PDF from one canonical Resume Document. It never falls back to deterministic or fictional product behavior.

The real Notion adapter has recording-based conformance coverage for Capture, Analysis, Resume Creation, relation-last commit, compensation, pagination, legacy analysis recovery, and safe provider errors. This is automated adapter evidence, not a claim that the current private workspace has passed a live mutation run.

## Remaining Operator Acceptance

1. run the complete automated final-app gate and frozen prototype gate from a clean checkout;
2. use [Operations](operations.md) to perform one bounded real Capture, Analysis, and Resume Creation smoke path with explicitly selected safe records;
3. record duplicate behavior, created/reused durable IDs, recovery status, revision, and fallback point using the [Cutover Evidence Template](cutover-evidence-template.md);
4. change default commands and current-operations documentation only after that evidence is accepted;
5. retain the prototype through the observation window before a separate retirement change.

## Follow-up Architecture Cleanup

The Fit Requirement and Resume Draft ports are task-specific, but their current Python signatures still exchange provider-ready message tuples and structured dictionaries. A later non-feature refactor should move prompt construction and initial Pydantic decoding fully into the DeepSeek adapters so the ports exchange only semantic workflow DTOs. The current workflow still validates every returned requirement, claim, role, and evidence ID before any artifact write; this cleanup does not block the implemented feature or cutover smoke path.

This keeps the application manageable: each workflow can be migrated and verified independently while the prototype remains the executable reference.
