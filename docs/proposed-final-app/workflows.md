# Proposed Final-App Workflows

Merida has three separate workflows behind three public module interfaces. The React dashboard and extension are adapters over those modules; Notion remains the record-management surface.

## 1. Application Capture

Surface: React Chrome MV3 side panel.

Module interface:

```python
ApplicationCapture.prepare(evidence)
ApplicationCapture.confirm(draft)
```

Flow:

1. The extension verifies its backend URL and Capture token.
2. **Fill Form** collects normalized Capture Evidence from the active tab.
3. `POST /api/v1/applications/prepare` canonicalizes the URL and returns safe review fields without writing.
4. The operator reviews Company Name, Role, optional Location, Job URL, and a readable Job Content preview.
5. **Create in Notion** calls `POST /api/v1/applications/confirm` with reviewed values and the in-memory Job Content.
6. The backend returns `created`, `already_captured`, `needs_review`, or a safe blocked/failed result.

Capture creates an Application with `Application Status = To Apply`, `Analyzed = false`, and no Match Score. Quick Capture is outside v1. Full Job Content is never persisted by the extension.

## 2. Application Analysis

Surface: Application Analysis section on React `/dashboard`.

Module interface:

```python
ApplicationAnalysis.get_queue(query)
ApplicationAnalysis.run_batch(limit)
```

Eligibility:

- `Application Status = To Apply`
- `Analyzed = false`
- readable Job Content

Flow:

1. `GET /api/v1/applications/analysis/queue?limit=5` returns an eligible-only preview, total count, and opaque cursor.
2. The operator chooses a batch limit from 1 through 10.
3. `POST /api/v1/applications/analysis/run` selects the backend's next eligible batch independently of the visible cursor.
4. Applications are processed sequentially with per-Application failure isolation.
5. The backend validates evidence, calculates Match Score deterministically, writes the body first, then commits final properties.
6. The route returns one final typed summary; there is no streamed dashboard transport.
7. On success, the dashboard resets both queues to page one so analyzed Applications can move into Resume Creation.

## 3. Resume Creation

Surface: Resume Creation section on React `/dashboard`.

Module interface:

```python
ResumeCreation.get_queue(query)
ResumeCreation.create(application_id)
```

Eligibility:

- `Application Status = To Apply`
- `Analyzed = true`
- no existing Resume Attachment
- readable Company Name, Role, Job Content, and Application Analysis

Flow:

1. `GET /api/v1/resumes/queue?limit=5` returns an eligible-only, Match Score-ordered queue.
2. The operator selects **Create Resume** on one Application.
3. `POST /api/v1/resumes/create` revalidates eligibility and returns `already_created` when the completion relation exists.
4. The workflow loads Master Resume evidence, extracts Fit Requirements, runs deterministic Matching, and blocks before writes when evidence is insufficient.
5. A validated Resume Document and Resume Fit Analysis are produced from evidence-backed claims.
6. The artifact committer creates the Resume, PDF, and Note, then attaches the final Application relation last.
7. Partial failures are compensated in reverse order and cleanup results are explicit.
8. The dashboard refreshes the queue but retains Resume, Note, and PDF output links.

## Demo And Real Modes

Demo mode exercises the same routes and workflow interfaces using deterministic local adapters and fictional data. It persists state in `app-data/demo/state.json` and PDFs in `app-data/export/`.

Real mode will use Notion and DeepSeek adapters behind the same workflow-owned interfaces. Until parity and cleanup suites pass, FastAPI reports real mode as blocked and the frozen Node prototype remains the real-workflow executable reference.
