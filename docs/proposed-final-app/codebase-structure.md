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
```

## Backend Layout

This is the logical ownership layout established by the module-seam decision
and the resolved runtime-topology decision. The backend is one `uv`-locked
installable Python project. The dashboard, extension, API client, and shared UI
are private npm workspace packages under one root lockfile.

```text
apps/api/merida_api/
  main.py
  app.py
  core/
    settings.py
    auth.py
    cors.py
    errors.py
  features/
    applications/
      router_capture.py
      router_analysis.py
      schemas.py
      capture.py
      analysis.py
      ports.py
      tests/
    job_postings/
      models.py
      parser.py
      capture_evidence.py
      tests/
    matching/
      models.py
      evidence_matching.py
      scoring_policy.py
      tests/
    resumes/
      router.py
      schemas.py
      creation.py
      ports.py
      fit_analysis.py
      application_ready_draft.py
      artifact_committer.py
      resume_blocks.py
      resume_template.py
      data/
        skill_normalization.json
      tests/
    notes/
      models.py
      resume_fit_analysis_note.py
      tests/
  integrations/
    notion_workspace.py
    deepseek_models.py
    pdf_export.py
    notion_relations.py
  shared/
    result.py
    ids.py
```

### Backend Rules

- `router_*.py` files parse HTTP input and call one module.
- `schemas.py` files hold Pydantic request and response models for a feature.
- Workflow modules return typed results, not FastAPI `Response` objects.
- Applications owns pursuit workflow orchestration; Job Postings owns source-opportunity parsing and values.
- Each workflow owns its narrow store and model interfaces in `ports.py`.
- Notion, DeepSeek, PDF, and filesystem adapters depend inward on those interfaces; deterministic fakes live under test support.
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
    dashboard/
      DashboardPage.tsx
      ReadinessPanel.tsx
      ApplicationAnalysisPanel.tsx
      ResumeCreationPanel.tsx
      dashboardQueries.ts
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

`packages/api-client` is generated from FastAPI OpenAPI. Manual wrappers live
next to generated source, but generated source is never edited by hand.

The canonical OpenAPI document and generated TypeScript source are committed so
contract changes are reviewable. Compiled client bundles, dashboard assets, and
extension assets are disposable ignored outputs. `final:check-generated`
regenerates the contract and fails on drift.

## Runtime And Commands

- Python 3.14.2 is the supported local runtime. Package metadata permits 3.10 through 3.14; a compatibility CI matrix is future work.
- Node 22.18 or newer is required by the generated-client toolchain.
- `uv.lock` is the Python resolution authority and the root `package-lock.json` is the TypeScript resolution authority.
- `final:dev` coordinates the reloadable FastAPI and dashboard processes; extension development uses an MV3 watch build.
- `final:build` produces the dashboard and independently loadable extension.
- `final:start` runs one FastAPI process that serves `/api/v1`, `/dashboard`, and PDF downloads.
- `test:final` verifies generated-client freshness, strict TypeScript, consumer tests, FastAPI tests, and both production builds without private credentials.
- Prototype `start` and `test` commands retain their existing meaning until final cutover.

## Module Interfaces

These are the interfaces implementation should protect.

### Application Capture

```python
class ApplicationCapture:
    async def prepare(self, evidence: CaptureEvidenceInput) -> CaptureDraft: ...
    async def confirm(self, draft: ConfirmedCaptureDraft) -> CaptureResult: ...
```

The module hides Job Posting parsing, confidence evaluation, URL
canonicalization, duplicate detection, schema validation, and workspace writes.
It does not expose a direct Quick Capture operation.

### Application Analysis

```python
class ApplicationAnalysis:
    async def get_queue(self, query: QueueQuery) -> ApplicationQueuePage: ...
    async def run_batch(self, limit: int) -> AnalysisRunSummary: ...
```

The module hides eligible queue selection, Job Content loading, task-specific
model calls, evidence validation, deterministic Match Score calculation,
body-first persistence, repair, and isolated per-Application failures. It
returns one final result and has no event-emitter seam.

### Resume Creation

```python
class ResumeCreation:
    async def get_queue(self, query: QueueQuery) -> ResumeQueuePage: ...
    async def create(self, application_id: str) -> ResumeCreationResult: ...
```

The module hides queue rules, Master Resume reads, Fit Requirement extraction,
Matching, Resume Fit Analysis, resume generation, claim-trace validation, and
artifact commit behavior.

### Workflow-owned store interfaces

There is no global workspace interface. Each workflow owns the smallest
semantic interface required by its implementation.

```python
class CaptureStore(Protocol):
    async def find_application_by_canonical_url(self, job_url: str) -> ApplicationRef | None: ...
    async def create_application(self, draft: ConfirmedCaptureDraft) -> ApplicationRef: ...

class ApplicationAnalysisStore(Protocol):
    async def get_queue(self, query: QueueQuery) -> ApplicationQueuePage: ...
    async def load_input(self, application_id: str) -> ApplicationAnalysisInput: ...
    async def commit(self, result: ValidatedApplicationAnalysis) -> None: ...

class ResumeCreationStore(Protocol):
    async def get_queue(self, query: QueueQuery) -> ResumeQueuePage: ...
    async def load_input(self, application_id: str) -> ResumeCreationInput: ...
    # Artifact operations used only by ResumeArtifactCommitter.
```

The Notion adapter and test-only fakes may implement every interface, but the composition
root injects only the relevant interface into each workflow. Exact operation
names may be refined by the Notion compatibility decision without widening the
interfaces or exposing Notion payloads.

### Matching and model interfaces

```python
class Matching:
    def match(
        self,
        targets: list[MatchTarget],
        evidence_items: list[EvidenceItem],
        scoring_policy: ScoringPolicy,
    ) -> MatchResult: ...

class ApplicationAnalysisModel(Protocol):
    async def analyze(self, job_content: JobContent) -> ProposedAnalysis: ...

class FitRequirementModel(Protocol):
    async def extract(
        self,
        job_content: JobContent,
        analysis: ApplicationAnalysisDocument,
    ) -> list[FitRequirement]: ...

class ResumeDraftModel(Protocol):
    async def generate(self, input: ValidatedDraftInput) -> ProposedResumeDraft: ...
```

Matching is deterministic and provider-independent. Model interfaces are
workflow-specific; DeepSeek adapters hide prompt and provider details, while deterministic model fakes remain test-only.

### Notes and artifact commit

```python
def create_resume_fit_analysis_note(
    fit_analysis: ResumeFitAnalysis,
    claim_traces: list[ClaimTrace],
) -> NoteDocument: ...

class ResumeArtifactCommitter:
    async def commit(self, bundle: ValidatedResumeBundle) -> ArtifactCommitResult: ...
```

The committer owns effect ordering, final attachment, reverse compensation, and
explicit cleanup reporting. It remains internal to Resumes rather than becoming
a generic transaction framework.

## Testing Surface

The interface is the test surface.

| Test type | Target |
| --- | --- |
| Backend module tests | Application Capture, Application Analysis, Matching, Resume Creation, Notes rendering, artifact commit. |
| Backend adapter tests | Narrow store conformance, Notion relation validation, fake behavior, task-specific model contracts. |
| Router tests | HTTP status, auth policy, request validation, and final response shape. |
| Frontend unit tests | Rendering, queue interactions, progress states, error states. |
| Extension tests | Capture Evidence collection, settings storage, API client calls. |
| End-to-end tests | ASGI Capture -> Analysis -> Resume Creation with injected boundary fakes. |

Prototype tests that only assert internal plumbing should be replaced as deeper module tests land.

## Naming Rules

- Use `Application`, `Job Posting`, `Job Content`, `Application Analysis`, `Resume Creation Queue`, `Master Resume`, `Job-Specific Resume`, `Resume Fit Analysis`, and `Resume Fit Analysis Note` exactly as the reviewed domain docs define them.
- Use `module`, `interface`, `seam`, and `adapter` for architecture docs.
- Avoid renaming domains just because the implementation language changes.
