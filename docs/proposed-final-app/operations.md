# Final App Operations

This guide operates the FastAPI, React dashboard, React Chrome extension, Notion, DeepSeek, PDF, and recovery runtime. Until a real cutover evidence record is accepted, `npm start` remains the frozen prototype and the final app remains under `final:*` commands.

## Setup

Requirements:

- Node 22.18 or newer and npm 11.11 or newer
- Python 3.14.2 for the supported local setup
- `uv` 0.11.28 or newer
- one Notion integration connected to the existing Applications, Resumes, and Notes databases
- one DeepSeek API key

Install `uv` before the first clean setup (`brew install uv` on macOS, or use the installer documented at <https://docs.astral.sh/uv/getting-started/installation/>). `uv` installs the pinned Python 3.14.2 environment. After setup, the checked-out `apps/api/.venv` is sufficient for normal start, verification, and recovery commands even when `uv` is temporarily unavailable. The package metadata remains compatible with Python 3.10 through 3.14 for future CI coverage, but this repository does not currently claim a compatibility CI matrix.

Copy `.env.example` to `.env` and set:

```text
API_HOST=127.0.0.1
API_PORT=8000
CAPTURE_TOKEN=<a unique local shared token>
NOTION_TOKEN=<integration token>
NOTION_DATABASE_ID=<Applications database id>
NOTION_RESUME_DATABASE_ID=<Resumes database id>
NOTION_NOTES_DATABASE_ID=<Notes database id>
DEEPSEEK_API_KEY=<DeepSeek key>
ANALYSIS_MODEL=deepseek-v4-flash
RESUME_MODEL=deepseek-v4-pro
LLM_INPUT_FORMAT=json
EXPORT_PATH=app-data/export
```

`API_HOST` must be loopback (`127.0.0.1`, another loopback address, `::1`, or `localhost`). The backend rejects non-loopback binding. `CAPTURE_TOKEN` is required and the placeholder `local-capture-token` is rejected.

Install and build:

```bash
npm run final:setup
npm run final:build
```

Start the one-worker runtime:

```bash
npm run final:start
```

Open `http://127.0.0.1:8000/dashboard`. Load `apps/extension/dist` as an unpacked extension and save the same backend URL and `CAPTURE_TOKEN` in extension settings.

## Readiness

Use these safe endpoints:

- `GET /api/v1/health` for the full process console
- `GET /api/v1/health/notion` for database compatibility
- `GET /api/v1/health/analysis` for Applications, Master Resume evidence, Matching, and DeepSeek Analysis
- `GET /api/v1/health/resumes` for the complete Resume workflow

Readiness is workflow-scoped. A Notes or Resume relation defect blocks Resume Creation without disabling Capture or Application Analysis. The extension uses Capture/Notion readiness only. Settings responses never expose tokens, database IDs, prompts, private content, or local paths.

## Automated Verification

Run before every smoke or cutover decision:

```bash
npm run test:final
npm test
```

The final gate regenerates OpenAPI and the TypeScript client, typechecks, lints, runs backend and frontend contract tests, executes one fixture-owned target regression for every required frozen parity ID, builds both React consumers, and scans shipped source/builds for demo surfaces. The prototype gate remains the source-observation oracle until retirement.

## Recovery

The effect journal is content-free and defaults to `app-data/recovery/effects.json`. Mutations block when the journal cannot be read safely or an Application has an unresolved operation.

Inspect unresolved entries:

```bash
npm run final:recovery -- inspect
```

Attempt targeted reconciliation only after stopping new mutations:

```bash
npm run final:recovery -- reconcile --run-id <run-id> --yes
```

Run `inspect` again. If an entry remains active, verify the listed safe Application, Resume, Note, and PDF identifiers directly in Notion and the export directory. Do not guess ownership and do not start the prototype mutating workflow while an effect is ambiguous.

After manual repair and fresh domain verification, acknowledge the exact entry:

```bash
npm run final:recovery -- acknowledge --run-id <run-id> --yes
```

Acknowledgement is not cleanup. It records that the operator verified and repaired provider state. Keep the cutover evidence record with the revision and recovery outcome.

## Bounded Real Smoke

Choose safe, explicitly identified records and run only one mutating runtime at a time.

1. Capture one posting through **Fill Form** and **Create in Notion**. Confirm the canonical URL duplicate returns the same Application.
2. Run Application Analysis for a batch limit of one. Inspect the three-sentence analysis, Skill Signal evidence, deterministic Match Score, and property-final state. Repeat only if the queue or recovery state requires it.
3. Create one Job-Specific Resume. Inspect preserved contact/non-work sections, role order, five-to-seven evidence-backed bullets per role, Resume Fit Analysis Note, PDF download, and final Application relation. Repeat and confirm `already_created` with no new artifacts.
4. Recheck all health endpoints, normal logs, and `recovery inspect`. Confirm there are no credentials, prompts, Job Content, Master Resume content, generated Resume text, raw provider payloads, or local paths in normal logs or public responses.
5. Record the result using `cutover-evidence-template.md` without copying private content.

## Cutover And Fallback

Do not switch default commands from the prototype until the automated gates, bounded real smoke, recovery inspection, and evidence record are accepted. Cutover changes command/documentation pointers; it does not rewrite valid Notion records.

Fallback during coexistence:

1. stop new final-app mutations;
2. inspect and reconcile the effect journal;
3. verify that no ambiguous operation remains for the selected Application;
4. run the frozen prototype for future operations;
5. keep completed final-app records authoritative so duplicate/idempotency rules return the existing result.

Retire the prototype only through a separate change after the observation window has representative Capture, Analysis, Resume, duplicate, restart, and recovery outcomes with no unresolved high-severity gaps.
