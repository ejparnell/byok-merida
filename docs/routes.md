# Routes

These are backend routes for the FastAPI app. They do not include React page routes such as `/dashboard`.

The locked v1 namespace is `/api/v1`. Paths below omit that prefix for readability, but callers use `/api/v1/...` exactly.

The FastAPI OpenAPI document is the wire-contract source of truth. Every public
operation has a stable `operationId` and a named Pydantic request or response
model. One generated Fetch package, `@merida/api-client`, serves both React
consumers through dashboard-owned and extension-owned adapters. Handwritten
route payload types and generic fetch layers are not part of the final app.

## Shared Route Rules

### JSON response shape

All JSON responses include `ok`, `validationFailures`, and `errors`. Successful
responses use `ok: true`; expected workflow blocks use `ok: false` with a typed
`status` and `result`; technical HTTP errors use the common `error` object.

All JSON success responses include:

```json
{
  "ok": true,
  "validationFailures": [],
  "errors": []
}
```

Routes may add `status`, `result`, `items`, `pagination`, or route-specific objects when useful.

Expected workflow blocks include:

```json
{
  "ok": false,
  "status": "blocked",
  "errors": ["Human-readable message."],
  "validationFailures": []
}
```

Routes may add route-specific fields such as `result`, `cleanup`, or an empty `items` list.

Technical HTTP errors use:

```json
{
  "ok": false,
  "error": {
    "code": "invalid_request",
    "message": "Request validation failed.",
    "requestId": null
  },
  "validationFailures": [
    {
      "kind": "request",
      "field": "limit",
      "message": "Input should be less than or equal to 10"
    }
  ],
  "errors": ["Request validation failed."]
}
```

`validationFailures` is a discriminated union. Request failures use
`kind=request`; safe backend configuration failures use `kind=configuration`;
and Notion schema failures use `kind=workspace_schema` with database and
property context. Clients branch on `status`, `result`, or `error.code`, never
on human-readable messages.

### HTTP status boundary

Expected workflow blocks may return `200` with `ok: false`. These are valid product outcomes, not backend crashes. Examples include insufficient Master Resume evidence and Notion schema readiness blocks. Capture `needs_review` is a successful review outcome with `ok: true`.

Technical and request failures should use HTTP status codes:

| HTTP status | Use for                                                                                       |
| ----------- | --------------------------------------------------------------------------------------------- |
| `400`       | `invalid_request` or `invalid_cursor`. FastAPI's default `422` body is not public.            |
| `401`       | `invalid_capture_token` for either a missing or invalid capture token.                        |
| `404`       | Requested PDF or backend-owned resource was not found.                                        |
| `405`       | `method_not_allowed` for a known route with the wrong HTTP method.                            |
| `409`       | Conflicting state that the route cannot safely treat as idempotent.                           |
| `413`       | Capture body or field exceeds the locked request limit.                                       |
| `415`       | A JSON-body route received an unsupported content type.                                       |
| `503`       | A required provider, workspace, or transactional spend-enforcement dependency is unavailable. |
| `500`       | Sanitized `internal_error` with a correlation `requestId`.                                    |

### Auth boundary

The v1 app is a local operator app.

- Protected Chrome extension capture routes require `X-Capture-Token`.
- Dashboard routes do not use the capture token.
- Dashboard routes are intended for the local same-origin React app talking to the local FastAPI backend.
- No user login or multi-user auth is planned for v1.
- No secrets are accepted from the frontend.

### CORS boundary

- Production dashboard traffic is same-origin.
- Development web origins and the installed `chrome-extension://` origin are explicit allow-list entries.
- Wildcard, reflected, and credentialed origins are forbidden.
- Browser preflight allows only `GET`, `POST`, `OPTIONS`, `Content-Type`, `X-Capture-Token`, and `Idempotency-Key`.
- Requests without an `Origin`, such as local CLI calls, remain possible; capture writes still require the token.

## Health Checks

Health checks are used by the React web app, Google Chrome extension, and local debugging.

The React `/dashboard` page should call `GET /health` for normal readiness state. Narrower health routes exist for diagnostics and tests.

`GET /health.status` is `blocked` if any dashboard workflow is blocked. The dashboard should still enable each section from its own check, such as `checks.analysis` or `checks.resumes`.

Queue counts are not returned from health routes. Queue inventory comes from `GET /applications/analysis/queue` and `GET /resumes/queue`.

| HTTP verb | Route              | Simple explanation                                                                                     |
| --------- | ------------------ | ------------------------------------------------------------------------------------------------------ |
| `GET`     | `/health`          | Returns the complete backend health summary.                                                           |
| `GET`     | `/health/notion`   | Validates Notion configuration and required database schemas.                                          |
| `GET`     | `/health/analysis` | Checks whether Application Analysis can run.                                                           |
| `GET`     | `/health/resumes`  | Checks whether Resume Creation can run, including Master Resume readiness and the fit-analysis module. |

### `GET /health`

Success:

```json
{
  "ok": true,
  "status": "ready",
  "service": "merida-api",
  "checks": {
    "settings": "ready",
    "notion": "ready",
    "analysis": "ready",
    "resumes": "ready"
  },
  "validationFailures": [],
  "errors": []
}
```

Failure:

```json
{
  "ok": false,
  "status": "blocked",
  "service": "merida-api",
  "checks": {
    "settings": "ready",
    "notion": "blocked",
    "analysis": "ready",
    "resumes": "blocked"
  },
  "validationFailures": [
    {
      "database": "Resumes",
      "property": "Application",
      "message": "Required relation property is missing."
    }
  ],
  "errors": [
    "Notion schema is invalid.",
    "Resume Creation is blocked until Notion is ready."
  ]
}
```

### `GET /health/notion`

Success:

```json
{
  "ok": true,
  "status": "ready",
  "workspace": "notion",
  "databases": {
    "applications": "ready",
    "resumes": "ready",
    "notes": "ready"
  },
  "validationFailures": [],
  "errors": []
}
```

Failure:

```json
{
  "ok": false,
  "status": "blocked",
  "workspace": "notion",
  "databases": {
    "applications": "ready",
    "resumes": "blocked",
    "notes": "not_checked"
  },
  "validationFailures": [
    {
      "database": "Resumes",
      "property": "Application",
      "message": "Required relation property is missing."
    }
  ],
  "errors": ["Resumes database is missing required property: Application."]
}
```

### `GET /health/analysis`

Application Analysis calculates `Match Score` by comparing validated Job Content Skill Signals with Master Resume evidence. Health therefore validates general Master Resume evidence readiness for analysis:

- exactly one `Master Resume` page exists
- the Master Resume body is readable
- some evidence can be extracted
- the deterministic evidence matcher is ready

Success:

```json
{
  "ok": true,
  "status": "ready",
  "workflow": "application_analysis",
  "checks": {
    "deepseek": "ready",
    "applicationsDatabase": "ready",
    "jobContentAccess": "ready",
    "masterResumeEvidence": "ready",
    "evidenceMatcher": "ready"
  },
  "validationFailures": [],
  "errors": []
}
```

Failure:

```json
{
  "ok": false,
  "status": "blocked",
  "workflow": "application_analysis",
  "checks": {
    "deepseek": "blocked",
    "applicationsDatabase": "ready",
    "jobContentAccess": "not_checked",
    "masterResumeEvidence": "not_checked",
    "evidenceMatcher": "not_checked"
  },
  "validationFailures": [],
  "errors": ["DEEPSEEK_API_KEY is not configured."]
}
```

### `GET /health/resumes`

Health validates general Master Resume readiness:

- exactly one `Master Resume` page exists
- the Master Resume body is readable
- at least one work-experience section is recognizable
- some bullet evidence can be extracted

Application-specific evidence sufficiency is checked by `POST /resumes/create`, not by health.

Success:

```json
{
  "ok": true,
  "status": "ready",
  "workflow": "resume_creation",
  "checks": {
    "deepseek": "ready",
    "notion": "ready",
    "fitAnalysis": "ready",
    "masterResume": "ready",
    "pdfExport": "ready"
  },
  "validationFailures": [],
  "errors": []
}
```

Failure:

```json
{
  "ok": false,
  "status": "blocked",
  "workflow": "resume_creation",
  "checks": {
    "deepseek": "ready",
    "notion": "ready",
    "fitAnalysis": "ready",
    "masterResume": "blocked",
    "pdfExport": "not_checked"
  },
  "validationFailures": [],
  "errors": ["Exactly one Master Resume page is required."]
}
```

## Operator Settings

These routes support the React operator app without exposing secrets.

| HTTP verb | Route                | Simple explanation                                        |
| --------- | -------------------- | --------------------------------------------------------- |
| `GET`     | `/operator/settings` | Returns non-secret backend settings for the operator app. |

### `GET /operator/settings`

Returns values the dashboard can safely display, such as selected model names and whether required dashboard providers are configured. It must not return capture tokens, Notion database IDs, Notion tokens, DeepSeek keys, prompts, export paths, or full private job content.

Model names are read-only in the dashboard. Model selection remains backend configuration.

Success:

```json
{
  "ok": true,
  "models": {
    "analysis": "deepseek-v4-flash",
    "resumes": "deepseek-v4-pro"
  },
  "configured": {
    "notion": true,
    "deepseek": true
  },
  "errors": []
}
```

## Applications

Application routes do not expose generic Notion CRUD. Editing and real management of Applications, Resumes, and Notes stays in Notion. Backend routes only support capture and LLM workflow execution.

### Capture

These routes are called by the React Chrome side panel. They require `X-Capture-Token` when called from the extension or curl.

Successful capture requires readable `Job Content`. If the extension cannot collect enough readable job content, the backend should return `needs_review` or a safe failure instead of creating a weak Application.

Capture sets new Applications to `Application Status = To Apply`. Analysis and Resume Creation never change `Application Status`.

| HTTP verb | Route                           | Simple explanation                                                   |
| --------- | ------------------------------- | -------------------------------------------------------------------- |
| `POST`    | `/applications/prepare`         | Parses captured page evidence without writing to the workspace.      |
| `GET`     | `/applications/capture-matches` | Finds existing Applications matching reviewed Company Name and Role. |
| `POST`    | `/applications/confirm`         | Writes a user-reviewed parsed Application to the workspace.          |

### `POST /applications/prepare`

Request body:

```json
{
  "evidence": {
    "url": "https://example.com/jobs/123",
    "title": "Senior Software Engineer",
    "selectedText": "",
    "visibleText": "ExampleCo is hiring a Senior Software Engineer..."
  }
}
```

The request may contain full captured page text. The response must not echo full `Job Content`.

Capture bodies are limited to `1 MiB`. URL is limited to `4,096` characters,
title to `1,000`, each evidence text field to `120,000`, and combined evidence
text to `240,000`. Oversized input returns `413 payload_too_large` without
echoing source content.

Success:

```json
{
  "ok": true,
  "result": "prepared",
  "draft": {
    "jobUrl": "https://example.com/jobs/123",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "location": "Remote",
    "jobContentPreview": "ExampleCo is hiring a Senior Software Engineer..."
  },
  "needsReview": false,
  "errors": []
}
```

An incomplete but reviewable parse is also HTTP `200` with `ok: true`, result
`needs_review`, `needsReview: true`, typed `missingFields`, safe
`reviewReasons`, and the partial draft. Prepare never writes to the workspace.

### `GET /applications/capture-matches`

The extension calls this protected, read-only route after a Review is prepared
or its Company Name or Role changes. It compares both fields against active
Applications using deterministic formatting and abbreviation normalization;
it excludes archived pages and Applications whose status is `Archived`.

The route returns `matched` with safe record summaries, `unmatched` with an
empty `matches` list, or a typed `blocked` response when Notion cannot be
checked. It never returns Job Content or creates, updates, archives, or
otherwise manages Notion records. A match is advisory: confirmation remains
available and the canonical Job URL duplicate rule is unchanged.

```json
{
  "ok": true,
  "result": "matched",
  "matches": [
    {
      "id": "app_123",
      "title": "Senior Engineer at ExampleCo",
      "companyName": "ExampleCo",
      "role": "Senior Engineer",
      "applicationStatus": "Applied",
      "url": "https://notion.so/example-application"
    }
  ],
  "errors": []
}
```

### `POST /applications/confirm`

Request body:

```json
{
  "draft": {
    "jobUrl": "https://example.com/jobs/123",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "location": "Remote",
    "jobContent": "ExampleCo is hiring a Senior Software Engineer..."
  }
}
```

Success:

```json
{
  "ok": true,
  "result": "created",
  "application": {
    "id": "app_123",
    "title": "Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "applicationStatus": "To Apply",
    "url": "https://notion.so/example-application"
  },
  "errors": []
}
```

Already captured:

```json
{
  "ok": true,
  "result": "already_captured",
  "application": {
    "id": "app_123",
    "title": "Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "applicationStatus": "To Apply",
    "url": "https://notion.so/example-application"
  },
  "errors": []
}
```

## Application Analysis

Application Analysis routes support the React `/dashboard` page. Analysis is a durable asynchronous enrichment workflow over already-captured Applications. The start target counts successful Analysis Completions; it is not a queue pagination or attempt limit.

The queue is eligible-only. Ineligible Applications stay out of the dashboard and should be managed in Notion.

| HTTP verb | Route                                        | Simple explanation                                                         |
| --------- | -------------------------------------------- | -------------------------------------------------------------------------- |
| `GET`     | `/applications/analysis/queue`               | Lists queued Applications for operator preview with cursor pagination.     |
| `POST`    | `/applications/analysis/run`                 | Creates or idempotently returns a durable Analysis Run and responds `202`. |
| `GET`     | `/applications/analysis/runs/active`         | Returns the active Analysis Run snapshot or `run: null`.                   |
| `GET`     | `/applications/analysis/runs/{runId}`        | Returns one current or terminal Analysis Run snapshot.                     |
| `POST`    | `/applications/analysis/runs/{runId}/cancel` | Requests cancellation and returns the run's current durable snapshot.      |

### `GET /applications/analysis/queue`

Query params:

| Name     | Required | Default | Notes                                                                          |
| -------- | -------- | ------- | ------------------------------------------------------------------------------ |
| `limit`  | No       | `5`     | Maximum number of Applications to return. Must be between `1` and `10`.        |
| `cursor` | No       | none    | Opaque cursor returned from the previous page. The frontend must not parse it. |

An Application is in the Application Analysis Queue when:

- `Application Status = To Apply`
- `Analyzed = false`
- the Application page has readable `Job Content`

Applications that already have a readable `Application Analysis` section but `Analyzed = false` are repair candidates. The Analysis Run repairs them without rerunning the LLM, and a completed repair counts toward its target.

Queue ordering:

1. `Date Found` ascending.
2. Stable internal tie-breaker, such as Application title or Notion page ID.

Success:

```json
{
  "ok": true,
  "queueCount": 12,
  "items": [
    {
      "applicationId": "app_123",
      "title": "Senior Software Engineer at ExampleCo",
      "companyName": "ExampleCo",
      "role": "Senior Software Engineer",
      "applicationStatus": "To Apply",
      "jobUrl": "https://example.com/jobs/123"
    }
  ],
  "pagination": {
    "limit": 5,
    "nextCursor": "cursor_456",
    "hasMore": true
  },
  "errors": []
}
```

### `POST /applications/analysis/run`

Required header:

```http
Idempotency-Key: 335a1d81-4d2c-48ba-98e6-e2ca4c878566
```

The dashboard generates one key for each intentional start. Automatic transport
behavior must not replay the POST with a new key.

Request body:

```json
{
  "target": 5
}
```

`target` defaults to `5` and must be between `1` and `10`. It is the number of
successful Analysis Completions the run pursues. The removed `limit` body field
is not an alias and is rejected. The unrelated queue-preview `limit` query
parameter remains supported by `GET /applications/analysis/queue`.

A newly accepted request returns `202` with a durable run snapshot before model
work finishes. Run creation captures the first
`min(eligible queue size, target × 2)` Application identities in canonical queue
order. That fixed Candidate Set is independent of the visible pagination cursor
and never admits later queue additions or reorderings.

Repeating the same key and target returns the same run without duplicating work.
Reusing a key with another target returns `409 idempotency_conflict`. A distinct
start while work is active returns `409 analysis_run_active` with `activeRunId`;
it does not queue or change the accepted target.

Accepted response:

```json
{
  "ok": true,
  "run": {
    "runId": "analysis_run_123",
    "lifecycle": "queued",
    "outcome": null,
    "reasonCode": null,
    "target": 5,
    "attemptBudget": 10,
    "createdAt": "2026-08-12T14:00:00Z",
    "updatedAt": "2026-08-12T14:00:00Z",
    "startedAt": null,
    "finishedAt": null,
    "progress": {
      "completions": 0,
      "repaired": 0,
      "evaluated": 0,
      "skipped": 0,
      "failed": 0,
      "indeterminate": 0
    },
    "spend": {
      "ceilingMicros": 500000,
      "committedMicros": 0,
      "verifiedCostMicros": 0,
      "activeReservationMicros": 0,
      "indeterminateReservationMicros": 0,
      "remainingAuthorizedMicros": 500000
    },
    "candidates": [
      {
        "applicationId": "app_123",
        "ordinal": 0,
        "state": "pending",
        "reasonCode": null,
        "startedAt": null,
        "completedAt": null
      }
    ]
  },
  "validationFailures": [],
  "errors": []
}
```

The worker reloads and revalidates each fixed candidate immediately before use,
processes candidates sequentially, and keeps at most one provider call in flight.
Newly analyzed and repaired Applications count after the readable body and final
properties commit. Skips and Candidate-Scoped Failures consume their candidate
slot but do not satisfy the target, so the worker may backfill within the fixed
Attempt Budget.

Every actual provider transmission, including retry and repair, must obtain a
transactional worst-case reservation before dispatch. One Application has at
most three actual transmissions, every call keeps thinking at high effort with
an 8,000-token reasoning-inclusive ceiling, and run Committed Spend never
exceeds 500,000 USD micros.

There is no NDJSON, SSE, or WebSocket transport. The run snapshot is the progress
interface. Its candidate entries and safe reason codes never include Job
Content, prompts, provider payloads, generated analysis, or model reasoning.

Active-run conflict:

```json
{
  "ok": false,
  "error": {
    "code": "analysis_run_active",
    "message": "An Analysis Run is already active.",
    "requestId": null,
    "activeRunId": "analysis_run_123"
  },
  "validationFailures": [],
  "errors": ["An Analysis Run is already active."]
}
```

### `GET /applications/analysis/runs/active`

Returns the same safe run snapshot shape as the start response. When no run is
active, success contains `"run": null`. Reloaded clients use this route to
reconnect without retaining a run ID.

### `GET /applications/analysis/runs/{runId}`

Returns the current or terminal snapshot for exactly one run. An unknown ID
returns the standard `404 not_found` envelope. A finished snapshot has exactly
one outcome: `target_met`, `spend_limited`, `attempt_budget_exhausted`,
`queue_exhausted`, `cancelled`, `authorization_blocked`, or `failed`.

Candidate states are `pending`, `evaluating`, `analyzed`, `repaired`, `skipped`,
`failed`, or `indeterminate`. `failed` at the run level is reserved for an
unrecoverable Run-Scoped Failure; ordinary candidate failures may coexist with
useful completions and a non-failed terminal outcome.

The `spend.committedMicros` field is the conservative sum of verified cost,
active reservations, and indeterminate reservations. It is not labeled as actual
cost. Restart recovery preserves this snapshot, reclaims queued and expired-lease
work, and reconciles uncertain sent calls before another dispatch.

### `POST /applications/analysis/runs/{runId}/cancel`

Requests cancellation for a queued, running, or cancelling run and returns its
current snapshot. Repeated cancellation is idempotent; cancelling a finished run
returns that terminal run unchanged. Cancellation prevents calls that have not
started, but does not promise to interrupt or refund an in-flight call. A valid
in-flight completion is committed and counted; an unreconcilable sent call is
recorded as indeterminate with its reservation still committed. The eventual
terminal outcome is `cancelled`, and all earlier completions remain intact.

## Resumes

Resume routes support the React `/dashboard` page. Resume Creation owns the queue rules, fit analysis, generated resume content, related Resume Fit Analysis Note, PDF export, and cleanup behavior.

Resume Creation is one-at-a-time for v1. There is no batch resume creation route.

Missing-PDF repair is out of v1. Applications with an existing Resume relation do not re-enter the Resume Creation Queue just because a PDF is missing.

| HTTP verb | Route                     | Simple explanation                                                               |
| --------- | ------------------------- | -------------------------------------------------------------------------------- |
| `GET`     | `/resumes/queue`          | Lists analyzed Applications eligible for Resume Creation with cursor pagination. |
| `POST`    | `/resumes/create`         | Creates a Job-Specific Resume for one queued Application.                        |
| `GET`     | `/resumes/{resumeId}/pdf` | Downloads the generated PDF for a created Job-Specific Resume.                   |

### `GET /resumes/queue`

Returns analyzed Applications that can show a **Create Resume** button on the React `/dashboard` page.

Query params:

| Name     | Required | Default | Notes                                                                          |
| -------- | -------- | ------- | ------------------------------------------------------------------------------ |
| `limit`  | No       | `5`     | Maximum number of Applications to return. Must be between `1` and `10`.        |
| `cursor` | No       | none    | Opaque cursor returned from the previous page. The frontend must not parse it. |

An Application is in the Resume Creation Queue when:

- `Application Status = To Apply`
- `Analyzed = true`
- the `Resumes` relation is empty
- Company Name and Role are present
- the Application page has readable `Job Content`
- the Application page has a readable `Application Analysis` section

Queue ordering:

1. `Match Score` descending.
2. `Date Found` ascending.
3. Stable internal tie-breaker, such as Application title or Notion page ID.

Success:

```json
{
  "ok": true,
  "queueCount": 7,
  "items": [
    {
      "applicationId": "app_123",
      "title": "Senior Software Engineer at ExampleCo",
      "companyName": "ExampleCo",
      "role": "Senior Software Engineer",
      "applicationStatus": "To Apply",
      "jobUrl": "https://example.com/jobs/123",
      "matchScore": 86,
      "analyzed": true,
      "hasResume": false
    }
  ],
  "pagination": {
    "limit": 5,
    "nextCursor": "cursor_789",
    "hasMore": true
  },
  "errors": []
}
```

Failure:

```json
{
  "ok": false,
  "status": "blocked",
  "items": [],
  "validationFailures": [
    {
      "database": "Resumes",
      "property": "Application",
      "message": "Required relation property is missing."
    }
  ],
  "errors": ["Resumes database is missing required property: Application."]
}
```

### `POST /resumes/create`

Request body:

```json
{
  "applicationId": "app_123"
}
```

Resume Creation sequence:

1. Load the Application identity and return one existing related Job-Specific Resume before schema, eligibility, model, or artifact work.
2. Validate the Resume workflow schema and revalidate Application eligibility.
3. Read Application `Job Content`, `Application Analysis`, and Master Resume evidence.
4. Extract and validate Fit Requirements, run deterministic Matching, and apply the evidence gate before creating artifacts.
5. Generate and validate role-owned claim traces, chronology, bullet counts, and the canonical Resume Document.
6. Create an unlinked Resume page with the employer-facing canonical Resume Document.
7. Export the PDF from that same canonical Resume Document.
8. Create the Resume Fit Analysis Note with its Application and Resume relations.
9. Attach the Resume-to-Application relation last as the durable completion marker.

The generated Resume body contains employer-facing content only. Fit analysis, evidence traces, gaps, and guardrails live in the related Note.

Success:

```json
{
  "ok": true,
  "result": "created",
  "application": {
    "id": "app_123",
    "title": "Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer"
  },
  "resume": {
    "id": "resume_123",
    "title": "Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "url": "https://notion.so/example-resume"
  },
  "note": {
    "id": "note_123",
    "title": "Resume Fit Analysis - Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "url": "https://notion.so/example-note"
  },
  "pdf": {
    "filename": "ExampleCo-Elizabeth-Parnell.pdf",
    "downloadUrl": "/api/v1/resumes/resume_123/pdf"
  },
  "errors": []
}
```

Already created:

```json
{
  "ok": true,
  "result": "already_created",
  "application": {
    "id": "app_123",
    "title": "Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer"
  },
  "resume": {
    "id": "resume_123",
    "title": "Senior Software Engineer at ExampleCo",
    "companyName": "ExampleCo",
    "role": "Senior Software Engineer",
    "url": "https://notion.so/example-resume"
  },
  "pdf": {
    "downloadUrl": "/api/v1/resumes/resume_123/pdf"
  },
  "errors": []
}
```

Failure:

```json
{
  "ok": false,
  "status": "blocked",
  "result": "blocked",
  "cleanup": {
    "status": "not_required",
    "errors": []
  },
  "validationFailures": [],
  "errors": ["Master Resume evidence cannot support enough Fit Requirements."]
}
```

### `GET /resumes/{resumeId}/pdf`

Success returns the PDF file itself with `Content-Type: application/pdf` and a download filename.

Failure:

```json
{
  "ok": false,
  "error": {
    "code": "pdf_not_found",
    "message": "Resume PDF was not found.",
    "requestId": null
  },
  "validationFailures": [],
  "errors": ["Resume PDF was not found."]
}
```

## Generated Client And Verification

- `@hey-api/openapi-ts` `0.99.0` and TypeScript `5.9.3` are pinned development dependencies.
- The accepted OpenAPI JSON and generated source are reproducible artifacts; generated files are read-only.
- Stable operation IDs determine SDK function names, and named Pydantic models determine exported TypeScript names.
- The generated package owns URL/query encoding, JSON serialization, response decoding, typed technical errors, and PDF typing.
- The dashboard adapter configures same-origin transport and never sends `X-Capture-Token`.
- The extension adapter configures the stored backend URL and sends `X-Capture-Token` to every protected capture operation: prepare, capture-match lookup, and confirm.
- Generated transport performs no automatic POST retries. Domain-key repeat behavior remains `already_captured` by canonical Job URL and `already_created` by existing final Resume relation.
- The deterministic FastAPI ASGI application and its emitted OpenAPI document are the highest contract test seam; both React builds must consume the same generated package.
