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

Readiness is workflow-scoped. A Notes or Resume relation defect blocks Resume Creation without disabling Capture. Analysis readiness also requires an approved exact DeepSeek endpoint/model rate card, current pricing evidence, its pinned tokenizer artifact, and a writable transactional Analysis Run Store. Missing or stale cost authority blocks transmission before provider spend. Settings responses never expose tokens, database IDs, prompts, private content, or local paths.

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

Application Analysis uses a separate content-free SQLite coordination store at
`app-data/recovery/analysis-runs.sqlite3`. It persists Analysis Run identity,
fixed Candidate Set, lifecycle, progress, leases, provider-call state, and
integer-micro spend reservations; it does not store Job Content, prompts,
provider payloads, generated analysis, or reasoning.

Normal backend startup automatically resumes queued Analysis Runs plus running
or cancelling runs whose leases expired. It reconciles or conservatively
consumes uncertain sent calls before authorizing new work. Do not delete or edit
the SQLite file, its `-wal`, or its `-shm` file to clear a run: doing so discards
the evidence needed to prevent duplicate paid work. Finished runs, including
runs with the `cancelled` outcome, never resume.

Use the dashboard's durable run snapshot to inspect lifecycle, outcome,
candidate results, and Committed Spend. Cancellation stops future transmissions
but cannot guarantee an in-flight provider request is stopped or refunded; wait
for the terminal snapshot before treating cancellation as complete.

### Resolve an Analysis commit quarantine

Merida durably quarantines an Application before each Notion Analysis mutation.
It removes the quarantine after a confirmed response, or automatically
reconciles it when the readable Analysis body is later visible. A quarantine
that remains after recovery means the remote result is unknown. It protects the
Application from a duplicate Analysis write in a later run.

First stop the backend and back up `analysis-runs.sqlite3` together with any
adjacent `-wal` and `-shm` files. Inspect only content-free coordination fields:

```sh
sqlite3 app-data/recovery/analysis-runs.sqlite3 \
  "SELECT q.application_id, q.run_id, q.created_at, c.state, c.reason_code, r.lifecycle, r.outcome FROM analysis_commit_quarantine AS q JOIN analysis_run_candidates AS c USING (run_id, application_id) JOIN analysis_runs AS r USING (run_id) ORDER BY q.created_at;"
```

Inspect the exact Application in Notion. If a readable Application Analysis is
present, leave the ledger untouched and restart Merida; normal reconciliation
clears the quarantine. An active recovered run repairs unfinished properties;
if the owning run is already terminal, a later Analysis Run repairs the partial
Application without another provider call.
If there is affirmative evidence that the request was never dispatched, or a
definitive provider rejection proves it could not have applied, an operator may
clear that one identity after recording the evidence:

```sh
sqlite3 app-data/recovery/analysis-runs.sqlite3 \
  "BEGIN IMMEDIATE; DELETE FROM analysis_commit_quarantine WHERE application_id = '<application-id>'; SELECT changes(); COMMIT;"
```

An absent Notion body and elapsed time are **not** proof of non-dispatch: a lost
or delayed request can still land later. Without affirmative evidence, keep the
quarantine. Deleting it anyway is a break-glass acceptance of duplicate-write
risk; retain the backup, monitor the Application for a late Analysis body, and
manually remove any duplicate section and repair its final properties before
resuming normal work.

## Bounded real-provider check

Choose safe, explicitly identified records and run one mutation at a time.

1. Capture one posting through **Fill Form** and **Create in Notion**. Confirm the canonical URL duplicate returns the same Application.
2. Start an Analysis Run with an Analysis Batch Target of one. Confirm the start returns immediately, follow the durable run to a terminal outcome, and inspect its analysis body, three-to-ten Skill Signal evidence set, deterministic Match Score, and final properties.
3. Create one Job-Specific Resume. Inspect preserved non-work sections, role order, evidence-backed bullets, Resume Fit Analysis Note, PDF, and final Application relation.
4. Repeat Resume Creation and confirm `already_created` with no new artifacts.
5. Recheck all health endpoints, normal logs, and `recovery inspect`.

Do not copy private Job Content, Master Resume text, generated Resume content, prompts, provider payloads, or credentials into operational notes.

## Troubleshooting

- **Dashboard missing:** run `npm run build`, then restart `npm start`.
- **Extension blocked:** verify the backend URL, Capture token, extension origin, and Notion Capture readiness.
- **Analysis blocked:** inspect `/api/v1/health/analysis`, provider configuration, approved model/rate-card validity, Analysis Run Store availability, Job Content, and Master Resume evidence readiness.
- **Analysis Run appears interrupted:** restart the one-worker backend and reconnect through the dashboard or `GET /api/v1/applications/analysis/runs/active`; do not start a replacement run or delete the ledger.
- **Analysis Run is spend limited:** preserve completed Applications and inspect Committed Spend. The backend stopped before a call whose full worst-case reservation could not fit under 500,000 USD micros.
- **Resume blocked:** inspect `/api/v1/health/resumes`, Application eligibility, Master Resume structure, Notes/Resume relations, and the recovery journal.
- **Invalid cursor:** refresh the dashboard; the client returns both queues to their first page once.
- **Unresolved operation:** stop mutations and use the recovery commands above before retrying.
