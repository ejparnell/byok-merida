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
  -> Job Postings modules
  -> Resumes modules
  -> Notes modules
  -> Notion workspace adapter
  -> Demo workspace adapter
  -> DeepSeek JSON module
  -> Resume Fit Analysis module
  -> PDF export module

Notion
  stores Job Postings, Resumes, and Notes

app-data/export/
  stores generated local resume PDFs
```

## Technology Stack

| Area | Proposed choice | Role |
| --- | --- | --- |
| Backend server | FastAPI | HTTP routing, request validation, OpenAPI schema, CORS, streaming, health checks. |
| Backend schemas | Pydantic | Request and response contracts, config validation, Notion DTOs. |
| Backend tests | pytest | Module tests, router tests, adapter tests, workflow regression tests. |
| Main frontend | React + TypeScript | Operator app for readiness, analysis batches, resume creation, review links, demo mode. |
| Frontend build | Vite | Fast local development and production static builds for the React app and extension UI. |
| API client | Generated from OpenAPI | Type-safe calls from React and the extension to FastAPI. |
| Extension | Chrome MV3 + React side panel | Capture active-tab evidence, review parsed fields, confirm writes. |
| Durable workspace | Notion | User-owned Job Postings, Resumes, and Notes databases. |
| Demo workspace | Local fixtures | Portfolio-safe mode with no private Notion data or secrets. |
| LLM provider | DeepSeek | Job Posting Analysis, Fit Requirement extraction, and resume generation. |
| Fit analysis | Python module | Local requirement/evidence matching, scoring, and normalization. |
| PDF export | Backend module | Creates application-ready PDFs after successful resume generation. |

## Design Principles

- **Workflow first**: preserve Capture, Job Posting Analysis, and Resume Creation as separate workflows.
- **Backend-owned secrets**: Notion and DeepSeek credentials never enter React state, extension storage, or browser logs.
- **Feature ownership**: Job Postings, Resumes, and Notes keep their domain language and module ownership.
- **Deep modules**: workflow rules sit behind small interfaces; routes and screens stay thin.
- **Evidence-backed output**: generated analysis and resumes must remain traceable to Job Content and Master Resume evidence.
- **Demoable without private data**: the final app should run in demo mode from checked-in fixtures.

## FastAPI Server Layer

FastAPI should expose HTTP routes through feature routers, but routes should not contain workflow rules. A route validates input, calls one domain module, and serializes the result.

Proposed top-level routers:

| Router | Paths | Thin adapter over |
| --- | --- | --- |
| `health` | `GET /api/health`, `GET /api/readiness` | App settings, workspace readiness, provider readiness. |
| `job_postings.capture` | `POST /api/job-postings/parse`, `POST /api/job-postings/capture`, `POST /api/job-postings/confirm` | Job Posting Capture module. |
| `job_postings.analysis` | `GET /api/job-postings/analysis/status`, `POST /api/job-postings/analysis/run` | Job Posting Analysis module. |
| `resumes` | `GET /api/resumes/status`, `POST /api/resumes/create` | Resume Creation module. |

Streaming analysis should use Server-Sent Events or JSON Lines through a single route-level streaming adapter. The Analysis Batch Run module should emit domain events without knowing the HTTP transport.

## React Operator App

The React app replaces backend-rendered local HTML pages. It should be a compact work surface, not a marketing dashboard.

Proposed routes:

| Route | Purpose |
| --- | --- |
| `/` | Workspace readiness and next actionable workflow. |
| `/analysis` | Queue count, batch limit, run progress, compact per-posting results. |
| `/resumes` | Resume Creation Queue, create action, links to created Resume, Note, and PDF. |
| `/settings` | Local backend URL, demo mode status, non-secret readiness checks. |

React should own interaction state, progress rendering, retry buttons, and navigation. It should not own Notion schema rules, queue rules, evidence validation, generation guardrails, or cleanup behavior.

## React Extension

The extension remains a Chrome side panel. React should own the side-panel UI, form state, and capture results. Chrome APIs and DOM extraction should stay behind extension modules that produce Capture Evidence.

Extension modules:

| Module | Interface | Hides |
| --- | --- | --- |
| Active Tab Evidence | `collectCaptureEvidence()` | `activeTab`, frame reads, selected text, visible text, semantic HTML. |
| Extension Settings | `getExtensionSettings()`, `saveExtensionSettings()` | Chrome storage and local defaults. |
| Capture Client | `parse(evidence)`, `capture(evidence)`, `confirm(parsed)` | Backend URL, capture token header, response normalization. |

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
| Job Posting Capture | `parse(evidence)`, `capture(evidence)`, `confirm(parsed)` | Workspace adapter, parser, Capture Evidence normalizer. |
| Capture Evidence | `create_capture_evidence(raw)` | Chrome extension payloads, future pasted text, demo fixtures. |
| Job Posting Analysis | `status()`, `run_batch(limit, emit)` | Workspace adapter, DeepSeek JSON module. |
| Job Posting Analysis Store | `get_status()`, `list_queue(limit)`, `load_input(id)`, `save_findings(id, findings)` | Notion adapter, demo adapter. |
| Resume Creation | `status()`, `create_for_job_posting(id)` | Workspace adapter, Resume Fit Analysis, resume LLM, PDF exporter. |
| Resume Fit Analysis | `health()`, `analyze(job_content, job_posting_analysis, master_evidence_items)` | Local scoring implementation, normalization dictionary. |
| Application-Ready Resume Draft | `create_draft(analysis, master_resume, generated_claims)` | Claim trace repair, role completion, template rendering. |
| Workspace | semantic methods per workflow | Notion adapter and demo adapter. |
| DeepSeek JSON | `request_json(prompt, schema, model)` | HTTP details, retry for empty content, model validation. |

The Workspace seam is justified because there are two real adapters: Notion for real use and demo fixtures for public demos and tests.

## Data And Storage

The final app should keep Notion as the v1 durable workspace, with a demo adapter that mirrors the same semantic interface.

Real mode:

- reads and writes existing Notion Job Postings, Resumes, and Notes databases
- validates schema before writes
- stores generated Job-Specific Resumes in Notion
- stores Resume Fit Analysis in related Notes
- writes PDFs to `app-data/export/`

Demo mode:

- reads checked-in sample Job Postings, Master Resume evidence, and Notes
- writes to local temporary state
- never calls Notion or DeepSeek unless explicitly configured
- supports screenshots, walkthroughs, and GitHub review without private data

## Auth And Local Trust

The current token policy maps cleanly to FastAPI dependencies.

| Caller | Auth policy |
| --- | --- |
| React operator app | Same-origin local browser requests. |
| Chrome extension | `X-Capture-Token` for capture, parse, and confirm. |
| CLI or curl | `X-Capture-Token` for protected write endpoints. |

FastAPI dependencies should own token validation, CORS origin checks, settings access, and current workspace adapter selection.

## API Contract Strategy

FastAPI should be the source of truth for HTTP contracts.

- Pydantic models define request and response bodies.
- OpenAPI generation provides the frontend contract.
- TypeScript API clients are generated from OpenAPI for the React app and extension.
- Contract tests compare key prototype responses with the new Pydantic models during migration.

## Portfolio Readiness

The final app should include:

- clear setup docs with `.env.example`
- demo mode that works without private secrets
- screenshots or a short demo video
- a concise architecture diagram
- CI for backend tests, frontend tests, type checks, and extension build
- sample data that demonstrates Capture, Analysis, Resume Creation, and PDF export safely
