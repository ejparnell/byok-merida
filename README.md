# Merida

Merida is a local-first operator application for turning captured job postings into evidence-backed application materials. It uses a FastAPI backend, a React dashboard, a React Chrome side-panel extension, Notion as the durable workspace, DeepSeek for bounded language-model workflows, and deterministic Python matching for evidence scoring.

The supported application has three workflows:

1. **Application Capture** — collect the active job page in Chrome, review parsed fields, and create or reuse the Application in Notion.
2. **Application Analysis** — run a bounded analysis batch over eligible Applications and persist evidence-backed analysis plus a deterministic Match Score.
3. **Resume Creation** — create one evidence-gated Job-Specific Resume, Resume Fit Analysis Note, and PDF for an eligible Application.

The dashboard is an LLM process console. Record editing and management remain in Notion.

## Runtime shape

```text
React Chrome side panel ─┐
                         ├─> FastAPI /api/v1
React /dashboard ────────┘      ├─> Notion
                                ├─> DeepSeek
                                └─> app-data/export + app-data/recovery
```

There is one product runtime. Missing provider configuration produces truthful blocked readiness; it never selects demo data or a fictional fallback. Credential-free tests inject deterministic fakes through the application factory.

## Requirements

- Node.js 22.18 or newer
- npm 11.11 or newer
- Python 3.14.2 for the supported local setup
- `uv` 0.11.28 or newer for a clean Python environment
- a Notion integration connected to the Applications, Resumes, and Notes databases
- a DeepSeek API key

## Setup

1. Copy `.env.example` to `.env` and configure the real provider values.
2. Install the locked Node and Python environments:

   ```sh
   npm run setup
   ```

3. Build the dashboard, extension, and generated client:

   ```sh
   npm run build
   ```

4. Start the application:

   ```sh
   npm start
   ```

5. Open `http://127.0.0.1:8000/dashboard`.
6. Load `apps/extension/dist` as an unpacked Chrome extension and save the same backend URL and `CAPTURE_TOKEN` in its settings.

See [Operations](docs/operations.md) for readiness, recovery, and bounded provider checks.

## Configuration

| Variable                    | Required                     | Purpose                                                            |
| --------------------------- | ---------------------------- | ------------------------------------------------------------------ |
| `API_HOST`                  | No                           | Loopback API host; defaults to `127.0.0.1`.                        |
| `API_PORT`                  | No                           | API port; defaults to `8000`.                                      |
| `WEB_ORIGIN`                | No                           | Allowed React development origin.                                  |
| `EXTENSION_ORIGIN`          | For installed extension CORS | Exact `chrome-extension://` origin.                                |
| `CAPTURE_TOKEN`             | Yes                          | Local shared token for protected Capture routes.                   |
| `NOTION_TOKEN`              | Yes                          | Notion integration token.                                          |
| `NOTION_DATABASE_ID`        | Yes                          | Applications database ID.                                          |
| `NOTION_RESUME_DATABASE_ID` | Analysis and Resumes         | Resumes database ID.                                               |
| `NOTION_NOTES_DATABASE_ID`  | Resume Creation              | Notes database ID.                                                 |
| `DEEPSEEK_API_KEY`          | Analysis and Resumes         | DeepSeek provider key.                                             |
| `ANALYSIS_MODEL`            | No                           | Analysis model; defaults to `deepseek-v4-flash`.                   |
| `RESUME_MODEL`              | No                           | Resume model; defaults to `deepseek-v4-pro`.                       |
| `EXPORT_PATH`               | No                           | PDF directory; defaults to `app-data/export`.                      |
| `RECOVERY_JOURNAL_PATH`     | No                           | Effect journal path; defaults to `app-data/recovery/effects.json`. |

Secrets stay in backend environment variables. The extension stores only the backend URL and Capture token.

## Commands

| Command                       | Purpose                                                                    |
| ----------------------------- | -------------------------------------------------------------------------- |
| `npm run setup`               | Install locked Node and Python environments.                               |
| `npm run dev`                 | Run the reloadable API and dashboard development processes.                |
| `npm run dev:extension`       | Build the MV3 extension in watch mode.                                     |
| `npm run build`               | Generate the client and build both React consumers.                        |
| `npm start`                   | Serve `/api/v1`, `/dashboard`, and PDF downloads from one FastAPI process. |
| `npm test`                    | Run the complete credential-free acceptance gate.                          |
| `npm run recovery -- inspect` | Inspect unresolved effect-journal entries.                                 |

## Repository map

| Path                                         | Ownership                                                             |
| -------------------------------------------- | --------------------------------------------------------------------- |
| `apps/api/merida_api/app.py`                 | FastAPI composition root and public routes.                           |
| `apps/api/merida_api/features/applications/` | Application Capture and Application Analysis.                         |
| `apps/api/merida_api/features/job_postings/` | Source-page parsing and canonical Job Posting values.                 |
| `apps/api/merida_api/features/resumes/`      | Resume Creation, evidence validation, and artifact commit.            |
| `apps/api/merida_api/matching/`              | Deterministic evidence matching and scoring.                          |
| `apps/api/merida_api/integrations/`          | Notion, DeepSeek, and PDF adapters.                                   |
| `apps/web/`                                  | React `/dashboard` process console.                                   |
| `apps/extension/`                            | React MV3 review-first Capture side panel.                            |
| `packages/api-client/`                       | OpenAPI document and generated shared TypeScript client.              |
| `packages/ui/`                               | Small shared React UI primitives.                                     |
| `scripts/`                                   | Setup, development, generation, verification, and runtime helpers.    |
| `docs/`                                      | Current architecture, workflow, schema, and operations documentation. |
| `reports/`                                   | Current repository audits.                                            |

## Verification

Run:

```sh
npm test
```

The gate checks generated-client freshness, TypeScript, lint and formatting, browser-session behavior, FastAPI workflows and adapters, both production builds, removed demo surfaces, and the final-only repository boundary.

## Documentation

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Codebase structure](docs/codebase-structure.md)
- [Routes](docs/routes.md)
- [Workflows](docs/workflows.md)
- [AI and ML workflows](docs/ai-workflows.md)
- [Frontend](docs/frontend.md)
- [Extension](docs/extension.md)
- [Notion schema](docs/notion-schema.md)
- [Operations](docs/operations.md)
- [Context map](CONTEXT-MAP.md)
