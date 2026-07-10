# Proposed Final App Workflows

The final app keeps the current operator sequence but moves the surfaces to React and the server layer to FastAPI.

## Daily Operator Sequence

1. Start the FastAPI backend.
2. Open the React operator app.
3. Use the React Chrome side panel to capture Job Postings.
4. Run Job Posting Analysis from the React `/analysis` page.
5. Create Job-Specific Resumes from the React `/resumes` page.
6. Review the created Resume, related Resume Fit Analysis Note, and PDF export.

Demo mode follows the same sequence but uses sample workspace data instead of private Notion records.

## Capture Workflow

Surface: React Chrome side panel.

Backend module: Job Posting Capture.

```text
Source Page
  -> extension collects Capture Evidence
  -> POST /api/job-postings/parse or /capture
  -> FastAPI validates request body
  -> Job Posting Capture module normalizes and parses evidence
  -> workspace adapter validates destination schema
  -> Notion or demo workspace stores Job Posting
  -> side panel shows Capture Result
```

### Direct Capture

Use direct capture when parsed fields are complete and confidence is high.

Expected result types:

- `created`
- `already_captured`
- `needs_review`
- `failed`

### Parse And Confirm

Use parse and confirm when the user wants to inspect or edit fields before writing.

```text
POST /api/job-postings/parse
  -> returns parsed fields without workspace writes

POST /api/job-postings/confirm
  -> validates reviewed fields
  -> deduplicates by canonical Job URL
  -> writes the Job Posting
```

The final app should preserve the current required creation fields:

- Job Posting title
- Job URL
- Job Content
- Company Name
- Job Title
- Location

## Job Posting Analysis Workflow

Surface: React `/analysis` page.

Backend module: Job Posting Analysis.

```text
GET /api/job-postings/analysis/status
  -> returns readiness, model, queue count, and blocking errors

POST /api/job-postings/analysis/run
  -> streams batch progress
  -> processes each queued Job Posting independently
  -> appends Job Posting Analysis before marking Analyzed true
```

### Eligibility

A Job Posting is in the Analysis Queue when:

- `Application Status = To Apply`
- `Analyzed = false`

If the page already has a `Job Posting Analysis` section but `Analyzed` is false, the workflow repairs the checkbox instead of duplicating analysis.

### React Page Behavior

The `/analysis` page should show:

- readiness state
- queue count
- selected model
- batch limit input
- run button
- streaming progress
- compact per-item result rows

The page should not show raw prompts, API keys, full private Job Content, or full model responses.

## Resume Creation Workflow

Surface: React `/resumes` page.

Backend module: Resume Creation.

```text
GET /api/resumes/status
  -> returns readiness, queue items, and blocking errors

POST /api/resumes/create
  -> reads Job Content and Job Posting Analysis
  -> reads the single Master Resume
  -> runs Resume Fit Analysis
  -> generates an Application-Ready Resume Draft
  -> validates claim traces
  -> writes Resume, Note, and PDF
  -> attaches Resume to Job Posting last
```

### Eligibility

A Job Posting appears in the Resume Creation Queue when:

- `Application Status = To Apply`
- `Analyzed = true`
- `Resumes` relation is empty
- Company Name and Job Title are present

### Guardrails

Resume Creation should fail before writing when:

- Job Content is missing
- Job Posting Analysis is missing
- no Master Resume exists
- more than one Master Resume exists
- Master Resume evidence is empty
- Master Resume evidence cannot support enough Fit Requirements
- configured work-experience roles are missing
- a configured role has fewer than five bullet evidence items
- generated claims cannot be traced to supported evidence

If a failure happens after writes begin, the backend should clean up draft records and local PDFs before returning the failure result.

### Successful Output

On success, the React page should show:

- created Job-Specific Resume link
- related Resume Fit Analysis Note link
- PDF export path
- concise success summary

The Job-Specific Resume remains employer-facing. Resume Fit Analysis remains in the related Note.

## Demo Workflow

Demo mode is required for a shareable GitHub and LinkedIn version.

Demo mode should:

- use sample Job Postings, Master Resume evidence, and Notes
- avoid private Notion data
- avoid requiring Notion tokens
- avoid requiring a DeepSeek key for the basic walkthrough
- optionally use recorded or deterministic analysis output
- allow reset from the React app

The demo path should exercise the same module interfaces as real mode. Only the adapters change.

## Error And Recovery Workflow

The final app should make errors actionable without exposing private data.

| Failure area | User-facing recovery |
| --- | --- |
| Backend offline | Start backend and retry readiness check. |
| Extension token invalid | Re-enter capture token in extension settings. |
| Notion schema invalid | Show missing property or relation names. |
| DeepSeek unavailable | Disable analysis and generation actions, keep capture available. |
| Fit evidence insufficient | Show unsupported requirement summary and point user to Master Resume evidence. |
| PDF export failed | Show local path/write permission hint and cleanup status. |

## Workflow Boundaries To Preserve

- Capture is not Job Posting Analysis.
- Job Posting Analysis is not Resume Fit Analysis.
- Resume Fit Analysis is not the employer-facing Job-Specific Resume.
- Notes store supporting analysis; Resumes store application-ready resume content.
- The Resume Attachment remains the durable proof that a Job-Specific Resume exists for a Job Posting.
