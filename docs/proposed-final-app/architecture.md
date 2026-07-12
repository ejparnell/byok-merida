# Proposed Final App Architecture

Merida should become a local-first, portfolio-ready application with a FastAPI backend, a React operator app, and a React Chrome side-panel extension.

The product contract stays the same: Merida turns captured Job Postings into evidence-backed application materials. The technology contract changes: FastAPI becomes the server layer, React owns user interfaces, and Python owns the fit-analysis implementation directly.

## Runtime Shape

```text
Chrome Source Page
  -> React Chrome side panel
    -> FastAPI backend

React operator app
  -> FastAPI backend

FastAPI backend
  -> Applications modules
  -> Job Postings source module
  -> Resumes modules
  -> Notes modules
  -> deterministic Matching module
  -> workflow-owned store and model interfaces
    <- Notion adapters and test-only store fakes
    <- DeepSeek adapters and test-only model fakes
    <- PDF and filesystem adapters

Notion
  stores Job Postings, Resumes, and Notes

app-data/export/
  stores generated local resume PDFs
```

## Technology Stack

| Area | Proposed choice | Role |
| --- | --- | --- |
| Backend server | FastAPI | HTTP routing, request validation, OpenAPI schema, CORS, final workflow responses, health checks. |
| Backend schemas | Pydantic | Request and response contracts, config validation, Notion DTOs. |
| Backend tests | pytest | Module tests, router tests, adapter tests, workflow regression tests. |
| Main frontend | React + TypeScript | Operator app for readiness, analysis batches, resume creation, and review links. |
| Frontend build | Vite | Fast local development and production static builds for the React app and extension UI. |
| API client | Generated from OpenAPI | Type-safe calls from React and the extension to FastAPI. |
| Extension | Chrome MV3 + React side panel | Capture active-tab evidence, review parsed fields, confirm writes. |
| Durable workspace | Notion | User-owned Job Postings, Resumes, and Notes databases. |
| Test support | Injected deterministic fakes | Credential-free verification without a second product runtime. |
| LLM provider | DeepSeek | Application Analysis, Fit Requirement extraction, and resume generation. |
| Fit analysis | Python module | Local requirement/evidence matching, scoring, and normalization. |
| PDF export | Backend module | Creates application-ready PDFs after successful resume generation. |

## Design Principles

- **Workflow first**: preserve Application Capture, Application Analysis, and Resume Creation as separate workflows.
- **Backend-owned secrets**: Notion and DeepSeek credentials never enter React state, extension storage, or browser logs.
- **Feature ownership**: Applications owns pursuit workflows, Job Postings owns source-opportunity behavior, Resumes owns resume generation, and Notes owns note documents.
- **Deep modules**: workflow rules sit behind small interfaces; routes and screens stay thin.
- **Evidence-backed output**: generated analysis and resumes must remain traceable to Job Content and Master Resume evidence.
- **Credential-free verification**: tests inject deterministic boundary fakes without exposing a second product runtime.

## FastAPI Server Layer

FastAPI should expose HTTP routes through feature routers, but routes should not contain workflow rules. A route validates input, calls one domain module, and serializes the result.

The top-level route adapters call the readiness, `ApplicationCapture`,
`ApplicationAnalysis`, and `ResumeCreation` modules. Exact paths, DTOs, and
generated-client names are owned by [Routes - Proposed](./routes.md) and the
public API contract decision. Application Analysis returns one final typed
summary; React owns the pending presentation and no streaming interface crosses
the workflow seam.

## React Operator App

The React app replaces backend-rendered local HTML pages. It should be a compact work surface, not a marketing dashboard.

The production web surface is one `/dashboard` LLM process console containing
readiness, Application Analysis, and Resume Creation. Editing and record
management remain in Notion.

React should own interaction state, progress rendering, retry buttons, and navigation. It should not own Notion schema rules, queue rules, evidence validation, generation guardrails, or cleanup behavior.

## React Extension

The extension remains a Chrome side panel. React should own the side-panel UI, form state, and capture results. Chrome APIs and DOM extraction should stay behind extension modules that produce Capture Evidence.

Extension modules:

| Module | Interface | Hides |
| --- | --- | --- |
| Active Tab Evidence | `collectCaptureEvidence()` | `activeTab`, frame reads, selected text, visible text, semantic HTML. |
| Extension Settings | `getExtensionSettings()`, `saveExtensionSettings()` | Chrome storage and local defaults. |
| Capture Client | `prepare(evidence)`, `confirm(draft)` | Backend URL, capture token header, response normalization. |

The side panel should only store:

- backend URL
- capture token
- non-secret display preferences

It must not store Notion tokens, database IDs, DeepSeek keys, prompts, or full private job content outside the current UI session.

## Deep Modules And Seams

The final app should make these modules explicit.

| Module | External interface | Important adapters |
| --- | --- | --- |
| Local Operator App | `create_app(settings, adapters)` | FastAPI app factory, CORS/auth policy, router composition. |
| Application Capture | `prepare(evidence)`, `confirm(draft)` | `CaptureStore`, Job Posting parser, and Notion adapter. |
| Capture Evidence | `create_capture_evidence(raw)` | Chrome extension payloads, future pasted text, and test fixtures. |
| Application Analysis | `get_queue(query)`, `run_batch(limit)` | `ApplicationAnalysisStore`, task-specific model adapter, Matching. |
| Resume Creation | `get_queue(query)`, `create(application_id)` | `ResumeCreationStore`, task-specific model adapters, Matching, Notes, artifact committer. |
| Matching | `match(targets, evidence_items, scoring_policy)` | Deterministic Python implementation, normalization dictionary. |
| Application-Ready Resume Draft | `create_draft(analysis, master_resume, generated_claims)` | Claim trace repair, role completion, template rendering. |
| Notes | `create_resume_fit_analysis_note(fit_analysis, claim_traces)` | Durable note structure and safe rendering. |
| Resume Artifact Committer | `commit(validated_bundle)` | Ordered Notion, PDF, relation, and reverse-compensation effects. |

There is no global `Workspace` interface. Capture, Application Analysis, and
Resume Creation each own a narrow semantic store interface. The Notion adapter
and test-only fakes may implement all three, but the composition root passes each workflow
only the interface it is allowed to use. Model interfaces are likewise
workflow-specific; shared DeepSeek infrastructure stays private to the adapter.

## Data And Storage

The final app keeps Notion as the only v1 durable product workspace. Test-only fakes mirror the workflow-owned interfaces for credential-free verification.

The product runtime:

- reads and writes existing Notion Job Postings, Resumes, and Notes databases
- validates schema before writes
- stores generated Job-Specific Resumes in Notion
- stores Resume Fit Analysis in related Notes
- writes PDFs to `app-data/export/`

Test composition:

- reads test-owned fictional Applications, Master Resume evidence, and Notes
- writes only to isolated temporary state
- never calls Notion or DeepSeek
- is available only through explicit dependency injection in tests

## Auth And Local Trust

The current token policy maps cleanly to FastAPI dependencies.

| Caller | Auth policy |
| --- | --- |
| React operator app | Same-origin local browser requests. |
| Chrome extension | `X-Capture-Token` for capture, parse, and confirm. |
| CLI or curl | `X-Capture-Token` for protected write endpoints. |

FastAPI dependencies should own token validation, CORS origin checks, and settings access. The production composition always selects the real workspace adapter.

## API Contract Strategy

FastAPI should be the source of truth for HTTP contracts.

- Pydantic models define request and response bodies.
- OpenAPI generation provides the frontend contract.
- TypeScript API clients are generated from OpenAPI for the React app and extension.
- Contract tests compare key prototype responses with the new Pydantic models during migration.

## Project Readiness

The final app should include:

- clear setup docs with `.env.example`
- screenshots or a short demo video
- a concise architecture diagram
- CI for backend tests, frontend tests, type checks, and extension build
- credential-free tests that demonstrate Capture, Analysis, Resume Creation, and PDF export safely
