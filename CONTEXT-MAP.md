# Merida Context Map

Merida uses `Application` for the pursuit record and `Job Posting` for the captured source opportunity. Notion remains the durable record-management surface; the application owns bounded Capture, Analysis, and Resume Creation workflows.

## Feature ownership

- **[Applications](apps/api/merida_api/features/applications/CONTEXT.md)** — owns Application Capture plus durable Application Analysis Run targeting, candidate execution, cost authorization, coordination, and restart recovery under `apps/api/merida_api/features/applications/`.
- **Job Postings** — owns source-page parsing, URL canonicalization, and captured Job Posting values under `apps/api/merida_api/features/job_postings/`.
- **[Resumes](apps/api/merida_api/features/resumes/CONTEXT.md)** — owns Resume Creation, Master Resume evidence extraction, Resume Fit Analysis, Resume documents, artifact commit, and recovery-scoped private artifact checkpoints under `apps/api/merida_api/features/resumes/`.
- **Matching** — owns deterministic evidence matching, normalization, and versioned scoring under `apps/api/merida_api/matching/`.
- **Integrations** — adapts the workflow-owned interfaces to Notion, DeepSeek, local PDF storage, and provider-safe errors under `apps/api/merida_api/integrations/`.
- **Dashboard** — owns the process-console interaction state under `apps/web/src/features/dashboard/`.
- **[Extension Capture](apps/extension/CONTEXT.md)** — owns active-tab evidence, local extension settings, and review-session state under `apps/extension/src/`.

## Shared contracts

- FastAPI and Pydantic own the HTTP contract.
- `packages/api-client` is generated from committed OpenAPI.
- `packages/ui` contains small display primitives shared by the two React consumers.
- `app-data/export` contains generated PDF artifacts. `app-data/recovery` contains the Applications-owned Analysis Run store and the independent Resumes-owned Resume Run coordination and spend store. Notion remains authoritative for Applications and completed Resume and Note pages; retained Resume Run and Artifact Set snapshots are content-free coordination history.

See [Architecture](docs/architecture.md), [Workflows](docs/workflows.md), and [Notion schema](docs/notion-schema.md) for the complete contract.
