# Proposed Final App

This folder describes the FastAPI and React target built from the working prototype. The current prototype docs remain in the parent `docs/` folder.

## Implementation Status

The first production-shaped vertical slice is implemented:

- FastAPI application factory and versioned REST routes under `/api/v1`
- persisted, resettable demo workspace with eligible-only queues
- review-first Application Capture with `X-Capture-Token`
- bounded Application Analysis with one final typed response
- one-at-a-time, idempotent Resume Creation with Resume, Note, and PDF outputs
- functional React `/dashboard` using the accepted Workflow Overview design
- functional React MV3 side panel using the accepted Focused Flow design
- OpenAPI schema, public-interface tests, production builds, and FastAPI static serving

Demo mode is complete and is the default. The existing real Notion and DeepSeek implementation remains in the frozen Node prototype while its behavior is migrated behind the new workflow-owned Python interfaces. The FastAPI app reports real mode as blocked instead of silently writing through an incomplete adapter. See [Implementation Review](implementation-review.md) for the review findings and remaining cutover work.

## Run The Implemented App

```bash
npm run final:setup
npm run final:build
npm run final:start
```

Open `http://127.0.0.1:8000/dashboard`. Load `apps/extension/dist` as an unpacked Chrome extension and set its Capture token to the backend `CAPTURE_TOKEN` value.

The final-app toolchain uses Python 3.14.2 locally, supports Python 3.10 through
3.14 in compatibility CI, requires Node 22.18 or newer with npm 11.11 or newer,
and requires `uv` 0.11.28 or newer for the one Python lockfile. npm workspaces
use one root lockfile for the web app, extension, generated API client, and
shared UI.

During migration, `npm start` and `npm test` continue to run the frozen
prototype. Final-app work stays under `final:*`; `npm run test:final` is the
credential-free acceptance gate.

The final app keeps the useful product shape that already works:

- capture Job Postings from Chrome
- enrich captured Job Content with Job Posting Analysis
- create evidence-backed Job-Specific Resumes from one Master Resume
- store durable workspace records in Notion
- keep secrets in the backend
- keep generated claims tied to source evidence

The proposed technology update is:

- FastAPI for the backend server layer
- React for the main operator frontend
- React for the Chrome extension side panel
- Python modules for Resume Fit Analysis instead of a separate Node-to-Python local seam
- generated TypeScript API types from the FastAPI OpenAPI schema

## Why This Shape

The prototype proved the workflow. The final app should make that workflow easier to understand, run, demo, and maintain.

The main architectural move is not "add more layers." It is to keep each workflow behind deep modules with small interfaces. FastAPI routes and React screens should be thin adapters over domain modules like Job Posting Capture, Job Posting Analysis, Resume Fit Analysis, and Resume Creation.

## Proposed Docs

- [Architecture](architecture.md): runtime shape, FastAPI/React responsibilities, seams, adapters, and HTTP surface.
- [Codebase Structure](codebase-structure.md): proposed folders, module ownership, interfaces, and testing surfaces.
- [Workflows](workflows.md): final operator workflows from Chrome capture through resume export.
- [AI And ML Workflows](ai-workflows.md): LangGraph orchestration, DeepSeek calls, TOON prompt encoding, deterministic ML scoring, validation, and recovery contracts.
- [Migration Plan](migration-plan.md): staged path from the prototype to the final app.
- [Implementation Review](implementation-review.md): reconciled review, implemented seams, verification, and remaining real-mode cutover.

## Scope Assumptions

- Notion remains the durable user workspace for the first shareable version.
- DeepSeek remains the configured LLM provider until a second provider is truly needed.
- The app remains local-first for v1, with a polished demo mode for GitHub and LinkedIn.
- The browser extension never stores Notion or DeepSeek secrets.
- The React web app replaces backend-served `/analysis` and `/resumes` pages.
- The React extension replaces the current handwritten side-panel UI.
- The backend owns validation, Notion writes, LLM calls, PDF export, and evidence guardrails.

## External References

- FastAPI docs: https://fastapi.tiangolo.com/
- React docs: https://react.dev/learn
- React with TypeScript: https://react.dev/learn/typescript
- Vite docs: https://vite.dev/guide/
- Chrome Side Panel API: https://developer.chrome.com/docs/extensions/reference/api/sidePanel
