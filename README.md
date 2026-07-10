# Merida

Merida is a local operator app for turning job postings into evidence-backed application materials. It captures job postings from Chrome into Notion, enriches captured postings with DeepSeek-backed analysis, and creates job-specific resumes from a Notion Master Resume using a local Resume Fit Analysis runtime.

The app is intentionally local-first:

- Chrome reads the current job page only after a button click.
- A Node backend on localhost owns Notion writes, DeepSeek calls, schema validation, and local operator pages.
- A Python runtime on localhost scores resume fit with repo-local normalization data.
- Notion remains the durable store for Job Postings, Resumes, and supporting Notes.
- Generated resume PDFs are written to the repo-local `export/` folder.

## What The App Does

Merida has three user-facing surfaces:

- **Chrome side panel**: captures the active job posting page, optionally lets the user review parsed fields, and writes a Job Posting page to Notion.
- **Job Posting Analysis page**: `http://127.0.0.1:3217/analysis` shows the To Apply analysis queue and runs a bounded sequential analysis batch.
- **Resume Creation page**: `http://127.0.0.1:3217/resumes` shows analyzed To Apply postings that do not yet have a related Resume and creates an application-ready Job-Specific Resume.

The main workflow is:

1. Capture a job posting into the configured Notion Job Postings database.
2. Run Job Posting Analysis against captured `Job Content`.
3. Create a Job-Specific Resume from the analyzed posting and the single `Master Resume`.
4. Review the generated Resume in Notion, the related Resume Fit Analysis Note, and the local PDF export.

## Runtime Shape

```text
Chrome extension side panel
  -> localhost Node backend
    -> Notion Job Postings database
    -> DeepSeek Job Posting Analysis
    -> Notion Resume and Notes databases
    -> localhost Python Resume Fit Analysis runtime
    -> export/*.pdf
```

The Node backend is plain Node HTTP, not Next.js or Express. It composes feature-owned route adapters from:

- `src/features/jobPostings`
- `src/features/resumes`
- `src/features/notes`

See [docs/architecture.md](docs/architecture.md) for the detailed architecture map.

## Quick Start

1. Install Node.js and Python 3.
2. Install the local Python fit runtime dependencies:

   ```sh
   npm run setup:ml
   ```

3. Copy `.env.example` to `.env` and fill in local values.
4. Configure the Notion databases described in [docs/notion-schema.md](docs/notion-schema.md).
5. Load the Chrome extension from `src/features/jobPostings/extension` as an unpacked extension.
6. Copy the extension ID from `chrome://extensions`.
7. Set `EXTENSION_ORIGIN=chrome-extension://<extension-id>` in `.env`.
8. Start the app:

   ```sh
   npm start
   ```

9. Open the extension options page and save:

   - Backend URL: `http://127.0.0.1:3217`
   - Capture token: the same value as `CAPTURE_TOKEN`

10. Check runtime health:

   ```sh
   curl -H "X-Capture-Token: <capture-token>" http://127.0.0.1:3217/health?validate=1
   curl http://127.0.0.1:3218/health
   ```

## Configuration

Merida reads `.env` from the repo root and then lets process environment variables override file values.

| Variable | Required | Used by | Purpose |
| --- | --- | --- | --- |
| `NOTION_TOKEN` | Yes | Node backend | Notion integration token. |
| `NOTION_DATABASE_ID` | Yes | Job Postings, Analysis, Resumes | Job Postings database ID. |
| `NOTION_RESUME_DATABASE_ID` | For `/resumes` | Resumes | Resume database ID. |
| `NOTION_NOTES_DATABASE_ID` | For `/resumes` | Notes | Notes database ID for Resume Fit Analysis Notes. |
| `CAPTURE_TOKEN` | Yes | Extension and backend | Shared local token for extension-origin writes. |
| `EXTENSION_ORIGIN` | Yes | Backend CORS | Exact Chrome extension origin. |
| `PORT` | Optional | Node backend | Backend port. Defaults to `3217`. |
| `FIT_RUNTIME_PORT` | Optional | Python runtime | Fit runtime port. Defaults to `3218`. |
| `FIT_RUNTIME_URL` | Optional | Node backend | Fit runtime URL. Defaults to `http://127.0.0.1:3218`. |
| `PYTHON_BIN` | Optional | `npm start` | Python executable for the fit runtime. Defaults to `.venv/bin/python`, then `python3`. |
| `DEEPSEEK_API_KEY` | For analysis and resumes | DeepSeek clients | Enables Job Posting Analysis and Resume generation. |
| `DEEPSEEK_MODEL` | Optional | DeepSeek clients | Supported values: `deepseek-v4-flash`, `deepseek-v4-pro`. |
| `DEBUG_CAPTURE` | Optional | Capture logs | Set `0` to reduce capture logging. |
| `DEBUG_ANALYSIS_CONTENT` | Optional | Analysis logs | Set `1` only when full extracted Job Content is needed in logs. |

Do not put Notion or DeepSeek secrets into the extension UI. The browser only stores the backend URL and `CAPTURE_TOKEN`.

## Commands

| Command | Purpose |
| --- | --- |
| `npm start` | Starts the Node backend and the Python fit runtime. |
| `npm run start:node` | Starts only the Node backend. Useful when the fit runtime is already running. |
| `npm run start:fit-runtime` | Starts only the Python fit runtime. |
| `npm run setup:ml` | Creates `.venv` and installs Python requirements. |
| `npm test` | Runs Node tests and Python fit runtime tests. |

## Operator Pages And Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health?validate=1` | `X-Capture-Token` | Checks backend config and optionally the Job Postings schema. |
| `POST` | `/capture` | `X-Capture-Token` | Captures and writes a Job Posting to Notion. |
| `POST` | `/parse` | `X-Capture-Token` | Parses page evidence for review without Notion writes. |
| `POST` | `/confirm` | `X-Capture-Token` | Writes reviewed parsed fields to Notion. |
| `GET` | `/analysis` | None | Serves the local Job Posting Analysis page. |
| `GET` | `/analysis/status` | None | Reads analysis readiness and queue count. |
| `POST` | `/analysis/run` | Same-origin local page | Streams analysis batch progress as NDJSON. |
| `GET` | `/resumes` | None | Serves the local Resume Creation page. |
| `GET` | `/resumes/status` | None | Reads resume workflow readiness and queue items. |
| `POST` | `/resumes/create` | Same-origin local page | Creates or returns a Job-Specific Resume for one Job Posting. |

See [docs/workflows.md](docs/workflows.md) for step-by-step workflow behavior and result types.

## Notion Data Model

Merida expects user-owned Notion databases. It validates schemas before writing, but it does not create or mutate database properties.

Required databases:

- **Job Postings**: captured postings, Job Content, Job Posting Analysis, application status, and inverse Resume/Note relations.
- **Resumes**: exactly one `Master Resume` plus Job-Specific Resumes.
- **Notes**: supporting analysis notes, including Resume Fit Analysis Notes.

Important relation names:

- Job Postings inverse relation to Resumes: `Resumes`
- Job Postings inverse relation to Notes: `Notes`
- Resumes inverse relation to Notes: `Notes`

See [docs/notion-schema.md](docs/notion-schema.md) for exact property names, types, and Master Resume requirements.

## Resume Generation Guardrails

`Create Resume` is designed to fail before writing a misleading resume. It requires:

- A ready Job Posting: `Application Status = To Apply`, `Analyzed = true`, and no related Resume.
- Existing `Job Content` and `Job Posting Analysis` blocks in the Job Posting page body.
- Exactly one Resume page named `Master Resume`.
- Master Resume evidence that supports enough required or responsibility Fit Requirements.
- Master Resume work-experience sections that match the configured resume template roles.
- At least five bullet evidence items per preserved Master Resume role.

On success, Merida writes:

- A clean employer-facing Job-Specific Resume page in Notion.
- A related Resume Fit Analysis Note in Notion.
- A local PDF export at `export/{CompanyName}-ElizabethParnell.pdf`.

The Resume page is attached back to the Job Posting only after the Resume, Note, and PDF write path succeeds.

## Project Map

| Path | Purpose |
| --- | --- |
| `src/backend` | Local Node server, config loading, route composition, auth and CORS policies. |
| `src/features/jobPostings` | Chrome extension, capture, parsing, Job Posting Notion client, Job Posting Analysis. |
| `src/features/resumes` | Resume queue, Resume Notion client, fit analysis orchestration, resume generation, PDF export. |
| `src/features/resumes/ml` | Local Python Resume Fit Analysis runtime. |
| `src/features/notes` | Notes Notion client and Resume Fit Analysis Note creation. |
| `src/lib/notionRelations.js` | Shared Notion relation-target validation. |
| `CONTEXT-MAP.md` | Domain context ownership map. |
| `src/features/*/CONTEXT.md` | Feature glossary and domain language. |
| `src/features/*/docs/adr` | Feature-local architectural decision records. |
| `report/` | Handoffs and architecture review artifacts. |
| `export/` | Generated local resume PDFs. |

## Documentation Index

- [Architecture](docs/architecture.md)
- [Workflows](docs/workflows.md)
- [Notion Schema](docs/notion-schema.md)
- [Operations And Troubleshooting](docs/operations.md)
- [Context Map](CONTEXT-MAP.md)
- [Job Postings Feature README](src/features/jobPostings/README.md)
- [Job Postings Glossary](src/features/jobPostings/CONTEXT.md)
- [Resumes Glossary](src/features/resumes/CONTEXT.md)
- [Notes Glossary](src/features/notes/CONTEXT.md)

## Verification

Run the full test suite with:

```sh
npm test
```

The suite covers backend routing, config, DeepSeek JSON parsing, Notion schema validation, capture parsing, analysis blocks, analysis store behavior, Resume Fit Analysis, resume generation guardrails, PDF export, and the Python fit runtime.

Some sandboxed environments block local server binding and can fail server tests with `listen EPERM`. If that happens, rerun verification in an environment that permits localhost binding before changing application logic.
