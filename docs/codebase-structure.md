# Codebase Structure

Merida is a Python backend plus two React consumers in one repository. The backend is one `uv`-locked project; the dashboard, extension, generated client, and shared UI are npm workspaces under one root lockfile.

```text
apps/
  api/
    merida_api/
      app.py
      cli.py
      core/
      features/
        applications/
        job_postings/
        resumes/
      integrations/
      matching/
      shared/
    tests/
  web/
    src/
      App.tsx
      features/dashboard/
      shared/api/
  extension/
    public/
    src/
      App.tsx
      session/
      shared/
packages/
  api-client/
  ui/
scripts/
docs/
reports/
app-data/
  export/
  recovery/
```

## Backend rules

- `app.py` is the composition root and HTTP adapter.
- Applications owns pursuit workflow orchestration.
- Job Postings owns source parsing and canonical source values.
- Resumes owns evidence gating, generation, rendering, and artifact commit.
- Matching is a deterministic provider-independent leaf.
- Each workflow owns narrow store/model protocols; the Notion and DeepSeek adapters depend inward on them.
- Routes serialize typed workflow results and do not own Notion payload construction or generation policy.
- Test fakes live only under `apps/api/tests/fakes` and enter through explicit application-factory injection.

## Frontend rules

- `apps/web/src/App.tsx` renders the dashboard; `dashboardSession.ts` owns its interaction state.
- `dashboardClient.ts` is the thin adapter over `@merida/api-client`.
- `apps/extension/src/App.tsx` renders the side panel; `captureSession.ts` owns review state.
- Chrome APIs and evidence collection stay under the extension's `shared/` boundary.
- Queue eligibility, schema validation, evidence validation, and cleanup remain backend responsibilities.

## Generated contract

`packages/api-client/openapi.json` and `packages/api-client/src/generated/` are committed, generated artifacts. `npm run check:generated` regenerates them and fails on drift. Handwritten operator-error normalization lives beside the generated source.

## Test seams

| Seam                     | Coverage                                                                           |
| ------------------------ | ---------------------------------------------------------------------------------- |
| FastAPI ASGI/OpenAPI     | auth, validation, readiness, routes, typed results, static dashboard serving       |
| Workflow modules         | Capture, Analysis, Matching, Resume Creation, artifact commit, recovery            |
| Provider adapters        | Notion recordings, DeepSeek structured output, PDF files                           |
| Dashboard session/client | queues, cursor recovery, batch limits, retained output links                       |
| Extension session/client | evidence limits, review preservation, dirty discard, Capture auth/readiness        |
| Repository acceptance    | generated freshness, typecheck, lint, tests, builds, no-demo and final-only checks |

## Commands

- `npm run dev` coordinates the reloadable API and dashboard.
- `npm run dev:extension` watches the MV3 build.
- `npm run build` produces the dashboard and independently loadable extension.
- `npm start` runs one FastAPI process serving `/api/v1`, `/dashboard`, and PDF downloads.
- `npm test` is the complete credential-free repository gate.
