# Merida Context Map

Merida uses `Application` for the pursuit record and `Job Posting` for the captured source opportunity. Notion remains the durable record-management surface; the application owns bounded Capture, Analysis, and Resume Creation workflows.

## Feature ownership

- **Applications** — owns Application Capture and Application Analysis orchestration under `apps/api/merida_api/features/applications/`.
- **Job Postings** — owns source-page parsing, URL canonicalization, and captured Job Posting values under `apps/api/merida_api/features/job_postings/`.
- **Resumes** — owns Resume Creation, Master Resume evidence extraction, Resume Fit Analysis, Resume documents, and artifact commit under `apps/api/merida_api/features/resumes/`.
- **Matching** — owns deterministic evidence matching, normalization, and versioned scoring under `apps/api/merida_api/matching/`.
- **Integrations** — adapts the workflow-owned interfaces to Notion, DeepSeek, local PDF storage, and provider-safe errors under `apps/api/merida_api/integrations/`.
- **Dashboard** — owns the process-console interaction state under `apps/web/src/features/dashboard/`.
- **[Extension Capture](apps/extension/CONTEXT.md)** — owns active-tab evidence, local extension settings, and review-session state under `apps/extension/src/`.

## Shared contracts

- FastAPI and Pydantic own the HTTP contract.
- `packages/api-client` is generated from committed OpenAPI.
- `packages/ui` contains small display primitives shared by the two React consumers.
- `app-data/export` and `app-data/recovery` are the only supported runtime artifact locations.

See [Architecture](docs/architecture.md), [Workflows](docs/workflows.md), and [Notion schema](docs/notion-schema.md) for the complete contract.
