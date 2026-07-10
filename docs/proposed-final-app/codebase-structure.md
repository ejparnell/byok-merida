# Proposed Codebase Structure

This structure keeps FastAPI, React, and the extension in one repo while preserving feature ownership.

The key rule: folders should follow domain ownership first, technology second. FastAPI routers and React screens are adapters. Workflow modules own behavior.

## Top-Level Layout

```text
apps/
  api/
    merida_api/
      main.py
      app.py
      core/
      features/
      integrations/
      shared/
    tests/
  web/
    src/
      app/
      features/
      shared/
  extension/
    src/
      side-panel/
      background/
      content/
      shared/
packages/
  api-client/
  ui/
  config/
docs/
  proposed-final-app/
app-data/
  export/
  demo/
```

## Backend Layout

```text
apps/api/merida_api/
  main.py
  app.py
  core/
    settings.py
    auth.py
    cors.py
    errors.py
    streaming.py
  features/
    job_postings/
      router_capture.py
      router_analysis.py
      schemas.py
      capture.py
      capture_evidence.py
      parser.py
      analysis.py
      analysis_store.py
      adapters/
        notion.py
        demo.py
      tests/
    resumes/
      router.py
      schemas.py
      creation.py
      fit_analysis.py
      application_ready_draft.py
      resume_blocks.py
      resume_template.py
      pdf_export.py
      data/
        skill_normalization.json
      adapters/
        notion.py
        demo.py
      tests/
    notes/
      schemas.py
      adapters/
        notion.py
        demo.py
      tests/
  integrations/
    deepseek_json.py
    notion_relations.py
  shared/
    result.py
    ids.py
```

### Backend Rules

- `router_*.py` files parse HTTP input and call one module.
- `schemas.py` files hold Pydantic request and response models for a feature.
- Workflow modules return typed results, not FastAPI `Response` objects.
- Notion-specific code stays in `adapters/notion.py`.
- Demo fixture code stays in `adapters/demo.py`.
- Shared integration modules are only for concepts used by multiple features.
- Feature tests target the module interface first, router behavior second.

## Frontend Layout

```text
apps/web/src/
  app/
    App.tsx
    routes.tsx
    providers.tsx
  features/
    workspace/
      WorkspaceHome.tsx
      readinessQueries.ts
    analysis/
      AnalysisPage.tsx
      AnalysisRunPanel.tsx
      analysisQueries.ts
    resumes/
      ResumesPage.tsx
      ResumeQueueTable.tsx
      resumeQueries.ts
    settings/
      SettingsPage.tsx
  shared/
    api/
    ui/
    hooks/
    formatting/
```

### Frontend Rules

- React pages own display and interaction state.
- React query hooks call generated API clients.
- UI primitives and pages do not know Notion property names.
- Queue eligibility, schema validation, cleanup rules, and evidence validation stay on the backend.
- Shared UI should be small and boring: buttons, inputs, status chips, tables, progress rows, dialogs.

## Extension Layout

```text
apps/extension/src/
  manifest.json
  side-panel/
    SidePanelApp.tsx
    CaptureActions.tsx
    ReviewForm.tsx
    CaptureResultView.tsx
  background/
    serviceWorker.ts
  content/
    collectFrameEvidence.ts
  shared/
    captureClient.ts
    extensionSettings.ts
    chromeTabs.ts
    captureEvidence.ts
```

### Extension Rules

- The side panel is React.
- Chrome API access is isolated in `shared/` and `content/`.
- Capture Evidence is normalized before it crosses the backend seam.
- Backend URL and capture token are the only required local settings.
- Extension code never embeds private prompts, Notion IDs, Notion tokens, or DeepSeek keys.

## Package Layout

```text
packages/
  api-client/
    generated/
    index.ts
  ui/
    Button.tsx
    StatusChip.tsx
    ProgressList.tsx
    Table.tsx
  config/
    eslint/
    typescript/
```

`packages/api-client` should be generated from FastAPI OpenAPI. Manual wrappers can live next to generated code, but generated files should be treated as disposable build output.

## Module Interfaces

These are the interfaces implementation should protect.

### Job Posting Capture

```python
class JobPostingCapture:
    async def parse(self, evidence: CaptureEvidenceInput) -> CaptureParseResult: ...
    async def capture(self, evidence: CaptureEvidenceInput) -> CaptureResult: ...
    async def confirm(self, parsed: ParsedJobPostingInput) -> CaptureResult: ...
```

The module hides evidence normalization, parser confidence, duplicate detection, schema validation, and workspace writes.

### Job Posting Analysis

```python
class JobPostingAnalysis:
    async def status(self) -> AnalysisStatus: ...
    async def run_batch(
        self,
        limit: int,
        emit: AnalysisEventEmitter,
    ) -> AnalysisRunSummary: ...
```

The module hides queue selection, Job Content loading, DeepSeek calls, evidence validation, append-before-marking, and isolated per-posting failures.

### Resume Creation

```python
class ResumeCreation:
    async def status(self) -> ResumeStatus: ...
    async def create_for_job_posting(
        self,
        job_posting_page_id: str,
    ) -> ResumeCreationResult: ...
```

The module hides queue rules, Master Resume reads, Fit Requirement extraction, Resume Fit Analysis, resume generation, claim-trace validation, Notion writes, PDF export, attachment, and cleanup.

### Workspace

The workspace seam should expose semantic operations, not CRUD plumbing.

```python
class Workspace:
    async def get_capture_readiness(self) -> CaptureReadiness: ...
    async def find_job_posting_by_url(self, job_url: str) -> JobPostingRef | None: ...
    async def create_job_posting(self, parsed: ParsedJobPosting) -> JobPostingRef: ...
    async def get_analysis_status(self) -> AnalysisStatus: ...
    async def list_analysis_queue(self, limit: int) -> list[JobPostingRef]: ...
    async def load_analysis_input(self, job_posting_id: str) -> AnalysisInput: ...
    async def save_analysis_findings(self, job_posting_id: str, findings: AnalysisFindings) -> None: ...
    async def get_resume_status(self) -> ResumeStatus: ...
    async def load_resume_creation_input(self, job_posting_id: str) -> ResumeCreationInput: ...
    async def save_resume_creation_output(self, output: ResumeCreationOutput) -> ResumeCreationRefs: ...
```

Notion and demo fixtures are adapters behind this seam.

## Testing Surface

The interface is the test surface.

| Test type | Target |
| --- | --- |
| Backend module tests | Capture, Analysis, Resume Fit Analysis, Resume Creation, PDF export. |
| Backend adapter tests | Notion relation validation, demo workspace behavior, DeepSeek JSON retries. |
| Router tests | HTTP status, auth policy, request validation, streaming shape. |
| Frontend unit tests | Rendering, queue interactions, progress states, error states. |
| Extension tests | Capture Evidence collection, settings storage, API client calls. |
| End-to-end tests | Demo mode Capture -> Analysis -> Resume Creation path. |

Prototype tests that only assert internal plumbing should be replaced as deeper module tests land.

## Naming Rules

- Use `Job Posting`, `Job Content`, `Job Posting Analysis`, `Resume Creation Queue`, `Master Resume`, `Job-Specific Resume`, `Resume Fit Analysis`, and `Resume Fit Analysis Note` exactly as the current domain docs define them.
- Use `module`, `interface`, `seam`, and `adapter` for architecture docs.
- Avoid renaming domains just because the implementation language changes.
