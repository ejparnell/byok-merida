# Routes - Proposed

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
  "errors": [
    "Human-readable message."
  ],
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
  "errors": [
    "Request validation failed."
  ]
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

| HTTP status | Use for |
| --- | --- |
| `400` | `invalid_request` or `invalid_cursor`. FastAPI's default `422` body is not public. |
| `401` | `invalid_capture_token` for either a missing or invalid capture token. |
| `404` | Requested PDF or backend-owned resource was not found. |
| `405` | `method_not_allowed` for a known route with the wrong HTTP method. |
| `409` | Conflicting state that the route cannot safely treat as idempotent. |
| `413` | Capture body or field exceeds the locked request limit. |
| `415` | A JSON-body route received an unsupported content type. |
| `500` | Sanitized `internal_error` with a correlation `requestId`. |

### Auth boundary

The v1 app is a local operator app.

- Chrome extension write routes require `X-Capture-Token`.
- Dashboard routes do not use the capture token.
- Dashboard routes are intended for the local same-origin React app talking to the local FastAPI backend.
- No user login or multi-user auth is planned for v1.
- No secrets are accepted from the frontend.

### CORS boundary

- Production dashboard traffic is same-origin.
- Development web origins and the installed `chrome-extension://` origin are explicit allow-list entries.
- Wildcard, reflected, and credentialed origins are forbidden.
- Browser preflight allows only `GET`, `POST`, `OPTIONS`, `Content-Type`, and `X-Capture-Token`.
- Requests without an `Origin`, such as local CLI calls, remain possible; capture writes still require the token.

## Health Checks

Health checks are used by the React web app, Google Chrome extension, and local debugging.

The React `/dashboard` page should call `GET /health` for normal readiness state. Narrower health routes exist for diagnostics and tests.

`GET /health.status` is `blocked` if any dashboard workflow is blocked. The dashboard should still enable each section from its own check, such as `checks.analysis` or `checks.resumes`.

Queue counts are not returned from health routes. Queue inventory comes from `GET /applications/analysis/queue` and `GET /resumes/queue`.

| HTTP verb | Route | Simple explanation |
| --- | --- | --- |
| `GET` | `/health` | Returns the complete backend health summary. |
| `GET` | `/health/notion` | Validates Notion configuration and required database schemas. |
| `GET` | `/health/analysis` | Checks whether Application Analysis can run. |
| `GET` | `/health/resumes` | Checks whether Resume Creation can run, including Master Resume readiness and the fit-analysis module. |

### `GET /health`

Success:

```json
{
  "ok": true,
  "status": "ready",
  "service": "merida-api",
  "mode": "real",
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
  "mode": "real",
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
  "errors": [
    "Resumes database is missing required property: Application."
  ]
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
  "errors": [
    "DEEPSEEK_API_KEY is not configured."
  ]
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
  "errors": [
    "Exactly one Master Resume page is required."
  ]
}
```

## Operator Settings

These routes support the React operator app without exposing secrets.

| HTTP verb | Route | Simple explanation |
| --- | --- | --- |
| `GET` | `/operator/settings` | Returns non-secret backend settings for the operator app. |

### `GET /operator/settings`

Returns values the dashboard can safely display, such as current workspace mode, selected model names, and whether required dashboard providers are configured. It must not return capture tokens, Notion database IDs, Notion tokens, DeepSeek keys, prompts, export paths, or full private job content.

Model names are read-only in the dashboard. Model selection remains backend configuration.

Success:

```json
{
  "ok": true,
  "mode": "real",
  "workspace": "notion",
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

| HTTP verb | Route | Simple explanation |
| --- | --- | --- |
| `POST` | `/applications/prepare` | Parses captured page evidence without writing to the workspace. |
| `POST` | `/applications/confirm` | Writes a user-reviewed parsed Application to the workspace. |

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

Application Analysis routes support the React `/dashboard` page. Analysis is a batch enrichment workflow over already-captured Applications.

The queue is eligible-only. Ineligible Applications stay out of the dashboard and should be managed in Notion.

| HTTP verb | Route | Simple explanation |
| --- | --- | --- |
| `GET` | `/applications/analysis/queue` | Lists queued Applications for operator preview with cursor pagination. |
| `POST` | `/applications/analysis/run` | Runs the backend's next eligible batch of Application Analysis and returns a final summary. |

### `GET /applications/analysis/queue`

Query params:

| Name | Required | Default | Notes |
| --- | --- | --- | --- |
| `limit` | No | `5` | Maximum number of Applications to return. Must be between `1` and `10`. |
| `cursor` | No | none | Opaque cursor returned from the previous page. The frontend must not parse it. |

An Application is in the Application Analysis Queue when:

- `Application Status = To Apply`
- `Analyzed = false`
- the Application page has readable `Job Content`

Applications that already have a readable `Application Analysis` section but `Analyzed = false` are repair candidates. `POST /applications/analysis/run` should repair them without rerunning the LLM.

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

Request body:

```json
{
  "limit": 5
}
```

`limit` defaults to `5` and must be between `1` and `10`.

The route processes the backend's next eligible batch by `limit`, independent of the dashboard's current pagination cursor. The visible queue is a preview, not a selection mechanism.

The route should process a bounded batch and return one final response. Each item failure should be isolated so one bad Application does not fail the whole batch.

There is no NDJSON, SSE, WebSocket, or automatic POST retry. The dashboard owns
pending presentation until this final response arrives.

The route does not intentionally rerun Application Analysis for already analyzed Applications. If it finds an existing readable `Application Analysis` section with `Analyzed = false`, it repairs the properties by setting `Analyzed = true` and recovering `Match Score` when possible. If the score cannot be recovered, `Match Score` should be left empty.

For new analysis work, the backend writes the `Application Analysis` body first. It sets `Match Score` and `Analyzed = true` as the final commit.

Success:

```json
{
  "ok": true,
  "result": "completed",
  "processed": 5,
  "succeeded": 4,
  "failed": 1,
  "repaired": 0,
  "items": [
    {
      "applicationId": "app_123",
      "title": "Senior Software Engineer at ExampleCo",
      "companyName": "ExampleCo",
      "role": "Senior Software Engineer",
      "result": "analyzed",
      "matchScore": 86,
      "errors": []
    },
    {
      "applicationId": "app_456",
      "title": "Platform Engineer at SampleCo",
      "companyName": "SampleCo",
      "role": "Platform Engineer",
      "result": "failed",
      "matchScore": null,
      "errors": [
        "Job Content section was not readable."
      ]
    }
  ],
  "errors": []
}
```

## Resumes

Resume routes support the React `/dashboard` page. Resume Creation owns the queue rules, fit analysis, generated resume content, related Resume Fit Analysis Note, PDF export, and cleanup behavior.

Resume Creation is one-at-a-time for v1. There is no batch resume creation route.

Missing-PDF repair is out of v1. Applications with an existing Resume relation do not re-enter the Resume Creation Queue just because a PDF is missing.

| HTTP verb | Route | Simple explanation |
| --- | --- | --- |
| `GET` | `/resumes/queue` | Lists analyzed Applications eligible for Resume Creation with cursor pagination. |
| `POST` | `/resumes/create` | Creates a Job-Specific Resume for one queued Application. |
| `GET` | `/resumes/{resumeId}/pdf` | Downloads the generated PDF for a created Job-Specific Resume. |

### `GET /resumes/queue`

Returns analyzed Applications that can show a **Create Resume** button on the React `/dashboard` page.

Query params:

| Name | Required | Default | Notes |
| --- | --- | --- | --- |
| `limit` | No | `5` | Maximum number of Applications to return. Must be between `1` and `10`. |
| `cursor` | No | none | Opaque cursor returned from the previous page. The frontend must not parse it. |

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
  "errors": [
    "Resumes database is missing required property: Application."
  ]
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

1. Verify the Application is eligible.
2. If a related Resume already exists, return `already_created` without creating a duplicate.
3. Read Application `Job Content` and `Application Analysis`.
4. Read Master Resume evidence.
5. Run fit analysis and evidence gating before creating any Notion or PDF artifacts.
6. If fit analysis blocks generation, return a workflow block with no draft artifacts.
7. Generate and validate resume content.
8. Create a draft Resume page.
9. Write employer-facing Resume body content.
10. Create the Resume Fit Analysis Note.
11. Export the PDF from the validated generated resume content object.
12. Attach final relations between Application, Resume, and Note as the final commit.

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
    "filename": "exampleco-senior-software-engineer.pdf",
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
  "errors": [
    "Master Resume evidence cannot support enough Fit Requirements."
  ]
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
  "errors": [
    "Resume PDF was not found."
  ]
}
```

## Generated Client And Verification

- `@hey-api/openapi-ts` `0.99.0` and TypeScript `5.9.3` are pinned development dependencies.
- The accepted OpenAPI JSON and generated source are reproducible artifacts; generated files are read-only.
- Stable operation IDs determine SDK function names, and named Pydantic models determine exported TypeScript names.
- The generated package owns URL/query encoding, JSON serialization, response decoding, typed technical errors, and PDF typing.
- The dashboard adapter configures same-origin transport and never sends `X-Capture-Token`.
- The extension adapter configures the stored backend URL and sends `X-Capture-Token` only to prepare and confirm.
- Generated transport performs no automatic POST retries. Domain-key repeat behavior remains `already_captured` by canonical Job URL and `already_created` by existing final Resume relation.
- The deterministic FastAPI ASGI application and its emitted OpenAPI document are the highest contract test seam; both React builds must consume the same generated package.
