# Proposed Final App

This folder describes a portfolio-ready version of Merida built from the working prototype. The current prototype docs remain in the parent `docs/` folder; these docs describe the proposed target app.

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
