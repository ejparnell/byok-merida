# Operations

This guide operates the supported FastAPI backend, React dashboard, React Chrome extension, Notion, DeepSeek, PDF, and recovery runtime.

Set `USER_NAME` in `.env` to the name that should appear in exported resume
filenames. New PDFs are saved under `app-data/export` as
`CompanyName-UserName.pdf`, with spaces and punctuation converted to hyphens.

## Setup

Requirements:

- Node 22.18 or newer and npm 11.11 or newer
- Python 3.14.2 for the supported local setup
- `uv` 0.11.28 or newer for a clean environment
- one Notion integration connected to the Applications, Resumes, and Notes databases
- one DeepSeek API key

Copy `.env.example` to `.env`, replace every placeholder, and keep the file private. `API_HOST` must be loopback. `CAPTURE_TOKEN` must be a unique local value; known placeholder values are rejected.

Install and build:

```sh
npm run setup
npm run build
```

Start the one-worker runtime:

```sh
npm start
```

Open `http://127.0.0.1:8000/dashboard`. Load `apps/extension/dist` as an unpacked extension and save the same backend URL and `CAPTURE_TOKEN` in extension settings.

## Readiness

Use these safe endpoints:

- `GET /api/v1/health` for complete readiness
- `GET /api/v1/health/notion` for database compatibility
- `GET /api/v1/health/analysis` for Application Analysis dependencies
- `GET /api/v1/health/resumes` for Resume Creation dependencies

Readiness is workflow-scoped. A Notes or Resume relation defect blocks Resume Creation without disabling Capture. Settings responses never expose tokens, database IDs, prompts, private content, or local paths.

## Verification

Run before provider smoke work and after every code change:

```sh
npm test
```

The gate regenerates OpenAPI and the TypeScript client, checks freshness, typechecks, lints, runs backend and browser-session tests, builds both React consumers, scans for removed demo surfaces, and verifies that no legacy runtime has returned.

## Recovery

The content-free effect journal defaults to `app-data/recovery/effects.json`. Mutations block when the journal cannot be read safely or an Application has an unresolved operation.

Inspect unresolved entries:

```sh
npm run recovery -- inspect
```

Attempt targeted reconciliation only after stopping new mutations:

```sh
npm run recovery -- reconcile --run-id <run-id> --yes
```

Run `inspect` again. If an entry remains active, verify the listed Application, Resume, Note, and PDF identifiers directly in Notion and `app-data/export`. Do not guess ownership.

After manual repair and fresh domain verification, acknowledge the exact entry:

```sh
npm run recovery -- acknowledge --run-id <run-id> --yes
```

Acknowledgement is not cleanup. It records that the operator verified and repaired provider state.

## Bounded real-provider check

Choose safe, explicitly identified records and run one mutation at a time.

1. Capture one posting through **Fill Form** and **Create in Notion**. Confirm the canonical URL duplicate returns the same Application.
2. Run Application Analysis with a batch limit of one. Inspect the analysis body, Skill Signal evidence, deterministic Match Score, and final properties.
3. Create one Job-Specific Resume. Inspect preserved non-work sections, role order, evidence-backed bullets, Resume Fit Analysis Note, PDF, and final Application relation.
4. Repeat Resume Creation and confirm `already_created` with no new artifacts.
5. Recheck all health endpoints, normal logs, and `recovery inspect`.

Do not copy private Job Content, Master Resume text, generated Resume content, prompts, provider payloads, or credentials into operational notes.

## Troubleshooting

- **Dashboard missing:** run `npm run build`, then restart `npm start`.
- **Extension blocked:** verify the backend URL, Capture token, extension origin, and Notion Capture readiness.
- **Analysis blocked:** inspect `/api/v1/health/analysis`, provider configuration, Job Content, and Master Resume evidence readiness.
- **Resume blocked:** inspect `/api/v1/health/resumes`, Application eligibility, Master Resume structure, Notes/Resume relations, and the recovery journal.
- **Invalid cursor:** refresh the dashboard; the client returns both queues to their first page once.
- **Unresolved operation:** stop mutations and use the recovery commands above before retrying.
