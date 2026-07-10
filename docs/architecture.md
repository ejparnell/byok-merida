# Architecture

Merida is a local operator application. It is built around a small Node HTTP backend, a Chrome side-panel extension, Notion as the durable workspace, DeepSeek for language analysis and generation, and a Python service for local Resume Fit Analysis scoring.

## Design Principles

- **Local operator first**: the UI is intentionally compact and runs on localhost.
- **Feature ownership**: Job Postings, Resumes, and Notes each own their own vocabulary, Notion adapters, and workflow code.
- **Notion as durable store**: Merida validates existing Notion database schemas but does not create or rewrite database properties.
- **Backend-owned secrets**: Notion and DeepSeek credentials stay in `.env` and are never entered into browser pages.
- **Evidence-backed output**: generated analysis and resumes are checked against source content and Master Resume evidence before writing.

## Runtime Components

```text
Chrome side panel
  captures current tab evidence
  sends /capture, /parse, /confirm with X-Capture-Token

Node backend
  serves /health, /analysis, /resumes
  validates config, CORS, and tokens
  owns Notion reads/writes
  owns DeepSeek calls
  calls the Python fit runtime

Python fit runtime
  serves /health, /fit/candidates, /fit/score
  loads src/features/resumes/data/skill-normalization.json
  computes requirement/evidence matching and fit scoring

Notion
  stores Job Postings, Resumes, and Notes

export/
  stores generated local resume PDFs
```

## Feature Ownership

| Feature | Owns | Key paths |
| --- | --- | --- |
| Job Postings | Captured job posting language, capture evidence, parsing, Job Content, Job Posting Analysis, analysis queue. | `src/features/jobPostings` |
| Resumes | Master Resume evidence, Resume Creation Queue, Resume Fit Analysis orchestration, Job-Specific Resume generation, PDF export. | `src/features/resumes` |
| Notes | Supporting analysis notes related to Job Postings and Resumes. | `src/features/notes` |

`CONTEXT-MAP.md` defines the domain boundaries and relationships. Feature-local `CONTEXT.md` files define stable terminology.

## Backend Composition

`src/backend/server.js` creates one plain Node HTTP server and composes feature adapters from `src/backend/adapters.js`.

Routes come from:

- `createJobPostingsAdapter()` in `src/features/jobPostings/backend/routes.js`
- `createResumesAdapter()` in `src/features/resumes/backend/routes.js`

The server owns:

- CORS allow-listing for same-origin pages and `EXTENSION_ORIGIN`.
- `X-Capture-Token` validation for extension writes.
- Same-origin token policy for local operator page POSTs.
- JSON request parsing.
- JSON, HTML, and NDJSON responses.
- Shared `/health` handling.

## Token Policies

| Policy | Meaning | Used by |
| --- | --- | --- |
| `none` | No `X-Capture-Token` required. | Static local pages and read-only status endpoints. |
| `required` | Requires `X-Capture-Token`. | Extension capture, parse, and confirm endpoints. |
| `same-origin` | Same-origin browser requests do not need the token; other origins do. | `/analysis/run`, `/resumes/create`. |

The browser extension still uses `X-Capture-Token` for all extension-origin backend calls.

## Startup

`npm start` runs `src/backend/start.js`, which starts:

1. The Python fit runtime from `src/features/resumes/ml/server.py`.
2. The Node backend from `src/backend/server.js`.

`PYTHON_BIN` defaults to `.venv/bin/python` when present, then `python3`.

Use `npm run start:node` or `npm run start:fit-runtime` when running the two processes separately.

## External Integrations

### Notion

Notion API access is implemented with feature-owned clients:

- `NotionClient` for Job Postings.
- `ResumeNotionClient` for Resumes and Job Posting resume relations.
- `NotesNotionClient` for Notes and Resume Fit Analysis Notes.

All clients use Notion API version `2022-06-28`.

The shared helper `src/lib/notionRelations.js` validates relation targets using current `relation.data_source_id`, older `relation.database_id`, configured database IDs, and returned database data source IDs.

### DeepSeek

DeepSeek is used for:

- Job Posting Analysis in `src/features/jobPostings/lib/deepseek.js`.
- Fit Requirement extraction and resume generation in `src/features/resumes/lib/deepseekResume.js`.

Supported model IDs are normalized and validated by `src/backend/deepseekModels.js`.

### Python Fit Runtime

The Node Resume workflow calls `FitRuntimeClient` in `src/features/resumes/lib/fitRuntime.js`.

Runtime endpoints:

- `GET /health`
- `POST /fit/candidates`
- `POST /fit/score`

The runtime loads `src/features/resumes/data/skill-normalization.json` once at startup. Restart `npm start` after changing the dictionary or Python analysis code.

## Workflow Data Flow

### Capture

```text
Chrome active tab
  -> frame evidence
  -> /capture or /parse
  -> parser normalizes title, company, role, URL, location, content
  -> Notion schema validation
  -> duplicate check by canonical Job URL
  -> Job Posting page creation or review response
```

Direct capture writes to Notion only when the parsed evidence meets minimum fields and confidence. The Fill Form path uses `/parse` to populate editable fields, then `/confirm` writes reviewed content.

### Job Posting Analysis

```text
/analysis/status
  -> validate config and Job Postings schema
  -> count To Apply, unanalyzed postings

/analysis/run
  -> query bounded analysis queue
  -> load Job Content from Notion blocks
  -> repair Analyzed checkbox if analysis already exists
  -> ask DeepSeek for JSON analysis
  -> validate evidence against Job Content
  -> append Job Posting Analysis blocks
  -> mark Analyzed checkbox true
```

`src/features/jobPostings/lib/analysisStore.js` owns the semantic Notion storage boundary for analysis. `analysisService.js` coordinates the batch and stream events.

### Resume Creation

```text
/resumes/status
  -> validate config, Resume schema, Notes schema
  -> check Python fit runtime health
  -> query analyzed To Apply postings with no related Resume

/resumes/create
  -> read Job Content and Job Posting Analysis
  -> find exactly one Master Resume
  -> extract Master Resume evidence
  -> extract Fit Requirements with DeepSeek
  -> score support with Python fit runtime
  -> generate application-ready resume with DeepSeek
  -> validate and repair claim traces
  -> write unlinked Resume page
  -> write related Resume Fit Analysis Note
  -> save local PDF
  -> attach Resume to Job Posting
```

The final attachment is intentionally last. If Note creation, PDF export, or attachment fails, the workflow archives the draft Resume, archives the Note when present, removes the PDF when present, and returns a failed result.

## Response Contracts

Capture result types live in `src/features/jobPostings/types/contracts.js`:

- `parsed`
- `created`
- `already_captured`
- `needs_review`
- `failed`

Analysis stream event types:

- `run_started`
- `item_started`
- `item_finished`
- `run_finished`

Analysis item result statuses:

- `analyzed`
- `skipped`
- `failed`
- `repaired`

Resume result types live in `src/features/resumes/types/contracts.js`:

- `created`
- `already_exists`
- `failed`

## Idempotency And Safety

- Capture deduplicates by canonical `Job URL`.
- Resume creation returns `already_exists` when the Job Posting already has a related Resume.
- Job Posting Analysis repairs the `Analyzed` checkbox if the page body already has a `Job Posting Analysis` section.
- Resume creation writes an unlinked Resume first and attaches it to the Job Posting only after the Resume, Note, and PDF succeed.
- Generated resume claims must map to supported Master Resume evidence.

## Where To Change Things

| Change | Start here |
| --- | --- |
| Add or rename Job Posting properties | `src/features/jobPostings/types/contracts.js`, `src/features/jobPostings/lib/notion.js`, docs and tests. |
| Change capture parsing | `src/features/jobPostings/lib/parser.js`, `captureEvidence.js`, parser/capture tests. |
| Change Job Posting Analysis output | `src/features/jobPostings/lib/analysisBlocks.js`, `deepseek.js`, analysis tests. |
| Change analysis persistence | `src/features/jobPostings/lib/analysisStore.js`. |
| Change Resume queue rules | `src/features/jobPostings/lib/resumeSource.js`. |
| Change Master Resume evidence extraction | `src/features/resumes/lib/resumeBlocks.js`. |
| Change resume template roles | `src/features/resumes/lib/resumeTemplate.js`. |
| Change fit scoring | `src/features/resumes/ml/analysis.py` and Python tests. |
| Change PDF output | `src/features/resumes/lib/pdfExport.js`. |

