# Lock the public API and generated-client contract

Type: grilling
Labels: ready-for-agent
Status: resolved
Blocked by: 02, 04
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

What exact API namespace, route ownership, request and response schemas, error
boundary, auth and CORS policy, pagination contract, idempotency surface,
transport behavior, and OpenAPI-generated client boundary should replace the
contradictory old and reviewed route descriptions?

## Problem Statement

Merida's reviewed final-app documents agree on the operator workflows but do not
yet provide one implementation-grade public contract. Older documents and the
prototype disagree about route names, streamed versus final responses, whether
workflow blocks are HTTP failures, which health route the extension may call,
how cursors behave, and whether the dashboard and extension maintain their own
handwritten request types.

Without a locked contract, the FastAPI routers, generated TypeScript client,
React dashboard, and React side panel could each implement a plausible but
incompatible interpretation. That would allow schema drift, accidental secret
exposure, unsafe automatic retries, brittle cursor handling, and UI behavior
that depends on human-readable error text instead of typed outcomes.

## Solution

Expose one versioned JSON API under `/api/v1`, described by named Pydantic
request and response models and stable OpenAPI operation IDs. Keep routes as thin
adapters over Readiness, Application Capture, Application Analysis, and Resume
Creation. Return one final typed response for each workflow, reserve HTTP errors
for invalid or technically unsuccessful requests, and represent expected
workflow blocks as typed `200` outcomes.

Generate one Fetch-based TypeScript package named `@merida/api-client` from the
accepted OpenAPI document. Both React consumers use that package through small
consumer-owned adapters; neither consumer defines route payload types or a
second generic fetch layer. The FastAPI ASGI application and its emitted OpenAPI
document form the single highest-level contract test seam.

## User Stories

1. As the local operator, I want one stable `/api/v1` namespace, so that the dashboard and extension do not depend on legacy prototype routes.
2. As the local operator, I want the dashboard and extension to interpret the same backend outcomes, so that an Application has consistent status everywhere.
3. As the local operator, I want Application Analysis to return one final summary, so that I can see a clear completed, partially completed, or blocked result.
4. As the local operator, I want Resume Creation to return typed output links, so that I can open the Resume, Resume Fit Analysis Note, and PDF safely.
5. As the local operator, I want duplicate Application confirmation to be a successful `already_captured` outcome, so that retrying a reviewed capture does not create duplicate records.
6. As the local operator, I want duplicate Resume Creation to be a successful `already_created` outcome, so that repeating the action does not create duplicate artifacts.
7. As the local operator, I want blocked workflows distinguished from backend crashes, so that I know when to fix configuration or evidence in Notion and when to retry the server.
8. As the local operator, I want readable validation failures, so that I can correct the exact request field, setting, database, or property that is invalid.
9. As the local operator, I want private Job Content omitted from responses, so that normal browser state and logs do not copy sensitive source material.
10. As the local operator, I want backend secrets omitted from every settings and error response, so that the browser never receives Notion or DeepSeek credentials.
11. As a dashboard user, I want same-origin API calls without a capture token, so that the dashboard remains a compact local operator surface.
12. As a dashboard user, I want readiness reported per workflow, so that one blocked workflow does not unnecessarily disable another ready workflow.
13. As a dashboard user, I want queue counts returned by queue routes rather than health routes, so that readiness and inventory remain separate concerns.
14. As a dashboard user, I want eligible-only queues, so that records needing management remain in Notion instead of leaking into the process console.
15. As a dashboard user, I want opaque cursor pagination, so that the backend may change its storage and ordering implementation without changing the UI contract.
16. As a dashboard user, I want invalid or stale cursors rejected clearly, so that the UI can reset to the first page instead of showing misleading data.
17. As a dashboard user, I want queue pages reset after a successful mutation, so that I do not continue browsing against stale eligibility state.
18. As a dashboard user, I want model names to be read-only, so that model selection and credentials remain backend configuration.
19. As an extension user, I want readiness checks to work without transmitting the capture token, so that the token is sent only where authorization is required.
20. As an extension user, I want prepare and confirm calls protected by `X-Capture-Token`, so that arbitrary webpages cannot write to my local workspace.
21. As an extension user, I want missing and invalid capture tokens to produce the same safe error, so that the API does not reveal token details.
22. As an extension user, I want `prepare` to return review fields without echoing full Job Content, so that I can review the Application without multiplying private content.
23. As an extension user, I want `confirm` to use the reviewed values and in-memory Job Content, so that the record reflects my corrections.
24. As an extension user, I want capture review needs represented as a typed result, so that the side panel does not scrape error messages to decide what to show.
25. As an extension user, I want CORS limited to configured extension and development origins, so that unrelated browser origins cannot call the local API.
26. As a frontend developer, I want stable OpenAPI operation IDs, so that generated function names do not change when Python function names are refactored.
27. As a frontend developer, I want named request and response models, so that the generated client does not collapse successful payloads into untyped dictionaries.
28. As a frontend developer, I want camelCase JSON fields generated from canonical backend models, so that both React apps use one consistent wire convention.
29. As a frontend developer, I want discriminated `result`, `status`, and error-code values, so that TypeScript can narrow outcomes without checking for arbitrary fields.
30. As a frontend developer, I want the generated client to own serialization and response decoding, so that each app does not maintain another fetch implementation.
31. As a frontend developer, I want consumer-owned dashboard and capture adapters, so that generated transport details do not leak into React components or session state.
32. As a frontend developer, I want generated files treated as read-only artifacts, so that local edits cannot silently diverge from FastAPI.
33. As a backend developer, I want each route to call one public workflow operation, so that routing does not accumulate eligibility, persistence, or LLM rules.
34. As a backend developer, I want one common technical error envelope, so that validation, authentication, cursor, not-found, conflict, and unexpected failures remain consistent.
35. As a backend developer, I want expected workflow blocks returned as route-specific typed models, so that cleanup and remediation context is not lost in a generic HTTP exception.
36. As a backend developer, I want POST requests to avoid automatic transport retries, so that non-idempotent work is never repeated by a generic client policy.
37. As a backend developer, I want semantic idempotency tied to canonical Job URL and existing Resume relations, so that v1 does not require a second client-generated identity system.
38. As a backend developer, I want PDF delivery modeled as binary content, so that OpenAPI and the generated client do not describe a file as JSON.
39. As a test author, I want one deterministic demo-mode API seam, so that real and demo adapters can be checked against the same observable HTTP behavior.
40. As a test author, I want the emitted OpenAPI document checked for breaking changes, so that route or schema drift fails before either React app is shipped.
41. As a test author, I want the generated client to typecheck and build in both consumers, so that a valid OpenAPI document is also proven usable.
42. As a maintainer, I want exact public contracts separated from repository placement, so that the runtime-topology decision can choose package roots without reopening API behavior.

## Implementation Decisions

### Namespace and route inventory

- `/api/v1` is the only public JSON and file API namespace for v1. Prototype paths, `/api/job-postings/*`, NDJSON routes, and unversioned workflow routes are not aliases and receive no compatibility layer.
- React page paths such as `/dashboard`, static assets, OpenAPI JSON, and interactive API documentation are application-serving concerns, not versioned workflow routes.
- The locked route inventory and OpenAPI operation IDs are:

| Method and route | Operation ID | Owner |
| --- | --- | --- |
| `GET /api/v1/health` | `getHealth` | Readiness |
| `GET /api/v1/health/notion` | `getNotionHealth` | Readiness |
| `GET /api/v1/health/analysis` | `getApplicationAnalysisHealth` | Readiness |
| `GET /api/v1/health/resumes` | `getResumeCreationHealth` | Readiness |
| `GET /api/v1/operator/settings` | `getOperatorSettings` | Operator configuration view |
| `POST /api/v1/applications/prepare` | `prepareApplication` | Application Capture |
| `POST /api/v1/applications/confirm` | `confirmApplication` | Application Capture |
| `GET /api/v1/applications/analysis/queue` | `getApplicationAnalysisQueue` | Application Analysis |
| `POST /api/v1/applications/analysis/run` | `runApplicationAnalysis` | Application Analysis |
| `GET /api/v1/resumes/queue` | `getResumeCreationQueue` | Resume Creation |
| `POST /api/v1/resumes/create` | `createResume` | Resume Creation |
| `GET /api/v1/resumes/{resumeId}/pdf` | `downloadResumePdf` | Resume Creation artifact delivery |
| `POST /api/v1/demo/reset` | `resetDemo` | Demo workspace administration |

- No generic Application, Job Posting, Resume, Note, Notion, prompt, model-selection, filesystem, or export-directory route is public in v1.
- `POST /api/v1/demo/reset` is present in the schema in both modes so the generated client is stable. It succeeds only in demo mode and returns `404 demo_not_active` in real mode.

### Wire conventions and common types

- JSON uses UTF-8, `application/json`, and camelCase field names. Python model names and internal snake_case fields do not leak onto the wire.
- IDs and cursors are opaque non-empty strings. Clients may compare IDs for equality but must not parse IDs or cursors.
- URLs to Notion and source pages are absolute HTTP(S) URLs. `pdf.downloadUrl` is a same-origin `/api/v1` path so the backend remains authoritative for local artifact delivery.
- Missing optional values use JSON `null`, not empty strings or absent keys, when the field is part of a response model. Request fields documented as optional may be omitted.
- Match Score is an integer from `0` through `100` or `null` when no score exists.
- Every JSON response includes `ok`, `errors`, and `validationFailures`. `errors` is always an array of safe human-readable strings. Clients branch on typed status, result, or error codes rather than error text.
- `validationFailures` is a discriminated union with three variants: request failures carry `kind=request`, `field`, and `message`; configuration failures carry `kind=configuration`, `setting`, and `message`; workspace schema failures carry `kind=workspace_schema`, `database`, nullable `property`, and `message`.
- Response models use literal values for `status`, `result`, workflow names, readiness checks, and per-item results so the generated TypeScript client produces discriminated unions.
- Response DTOs must be named Pydantic models. Returning untyped dictionaries from public routes is not accepted because it prevents useful OpenAPI generation.
- Public models do not contain Notion payloads, prompt text, raw model responses, auth headers, capture tokens, API keys, database IDs, local filesystem paths, full Job Content, Master Resume content, generated Resume text, or claim evidence bodies.

### Readiness and operator settings schemas

- `HealthResponse` contains `ok`, `status`, fixed service name, `mode`, `checks`, `validationFailures`, and `errors`. The exact root checks are `settings`, `notion`, `analysis`, and `resumes`, each with `ready`, `blocked`, or `not_checked`.
- Root health is `blocked` when any dashboard workflow is blocked, but consumers enable Capture, Application Analysis, and Resume Creation from the relevant individual check rather than the aggregate status.
- `NotionHealthResponse` contains `workspace`, exact database checks for `applications`, `resumes`, and `notes`, plus the common response fields.
- `ApplicationAnalysisHealthResponse` uses workflow `application_analysis` and exact checks for `deepseek`, `applicationsDatabase`, `jobContentAccess`, `masterResumeEvidence`, and `evidenceMatcher`.
- `ResumeCreationHealthResponse` uses workflow `resume_creation` and exact checks for `deepseek`, `notion`, `fitAnalysis`, `masterResume`, and `pdfExport`.
- Health routes return HTTP `200` in both ready and blocked states. A blocked health response uses `ok=false` and `status=blocked` with safe remediation details.
- Queue counts never appear in health responses.
- `OperatorSettingsResponse` contains `mode`, `workspace`, read-only `models.analysis`, read-only `models.resumes`, `configured.notion`, and `configured.deepseek`, plus the common response fields. It never includes secret values, secret-presence hints beyond those booleans, database IDs, prompts, or export paths.

### Application Capture schemas

- `PrepareApplicationRequest` contains one `evidence` object. `evidence.url` is a required HTTP(S) URL. `title`, `selectedText`, `visibleText`, and `semanticHtml` are optional strings defaulting to empty. At least one of selected text, visible text, or semantic HTML must contain readable evidence.
- Capture requests are limited to a `1 MiB` encoded JSON body. `url` is limited to `4,096` characters, `title` to `1,000`, each evidence text field to `120,000`, and all evidence text fields together to `240,000`. The extension truncates before transport, while the API rejects an oversized body or field with `413 payload_too_large` rather than silently truncating it.
- `PrepareApplicationResponse` returns result `prepared` or `needs_review`, a `needsReview` boolean, `reviewReasons`, `missingFields`, and a draft containing canonical `jobUrl`, nullable `companyName`, nullable `role`, nullable `location`, and a bounded `jobContentPreview`.
- Prepare never writes to the workspace and never returns full Job Content, raw HTML, parser confidence internals, or raw provider output.
- A successfully parsed but incomplete draft is an HTTP `200` product outcome with `ok=true`, `result=needs_review`, and populated review fields. Malformed transport input remains a `400 invalid_request`.
- `ConfirmApplicationRequest` contains a `draft` with required canonical `jobUrl`, `companyName`, `role`, and readable `jobContent`; `location` is nullable. `jobUrl` is limited to `4,096` characters, Company Name and Role to `200` each, Location to `300`, and Job Content to `20..120,000` trimmed characters. The server trims and revalidates every field and canonicalizes the URL again before duplicate detection.
- `ConfirmApplicationResponse` is a union of `created`, `already_captured`, and `blocked`. Created and already-captured outcomes use `ok=true` and include an Application summary with `id`, `title`, `companyName`, `role`, nullable `location`, `jobUrl`, fixed default `applicationStatus=To Apply`, and Notion `url`.
- `already_captured` is selected by canonical Job URL and returns the existing Application. It is not an HTTP conflict.
- A valid request that cannot write because the configured workspace is blocked returns HTTP `200`, `ok=false`, `status=blocked`, `result=blocked`, and typed validation failures. User-correctable field failures are `400 invalid_request` rather than a second confirm-time review protocol.

### Application Analysis schemas

- `GetApplicationAnalysisQueueResponse` is a ready-or-blocked union. The ready variant contains `queueCount`, `items`, `pagination`, and the common response fields. The blocked variant contains `ok=false`, `status=blocked`, `queueCount=0`, an empty item list, first-page pagination, and remediation details. Each ready item contains `applicationId`, `title`, `companyName`, `role`, `applicationStatus`, and `jobUrl`.
- `RunApplicationAnalysisRequest` contains `limit`, defaulting to `5` and constrained to `1..10`. It never accepts a cursor or client-selected Application IDs; the visible queue is a preview.
- `RunApplicationAnalysisResponse` is a union of `completed` and `blocked`. Completed includes `processed`, `succeeded`, `failed`, `repaired`, and item results. The count fields must reconcile with the item list.
- Each analysis item contains `applicationId`, `title`, `companyName`, `role`, result `analyzed`, `repaired`, `skipped`, or `failed`, nullable `matchScore`, and safe `errors`.
- A run with zero eligible Applications is a successful completed response with zero counts and an empty item list.
- Per-Application failures do not change the HTTP status or prevent other items from completing. A workflow-wide readiness block returns HTTP `200`, `ok=false`, `status=blocked`, result `blocked`, zero counts, and no items.
- Application Analysis returns one final JSON response. SSE, WebSockets, NDJSON, event emitters, and streamed progress are not public v1 transports.

### Resume Creation schemas

- `GetResumeCreationQueueResponse` is a ready-or-blocked union with the same blocked queue shape as Application Analysis. Its ready variant contains `queueCount`, `items`, `pagination`, and the common response fields. Each ready item contains `applicationId`, `title`, `companyName`, `role`, `applicationStatus`, `jobUrl`, `matchScore`, fixed `analyzed=true`, and fixed `hasResume=false`.
- `CreateResumeRequest` contains exactly one required `applicationId`. Batch IDs, a cursor, model selection, prompt input, and client-provided content are not accepted.
- `CreateResumeResponse` is a union of `created`, `already_created`, `blocked`, and `failed`.
- `created` uses `ok=true` and returns summaries for the Application, Job-Specific Resume, Resume Fit Analysis Note, and PDF. The Application summary contains `id`, `title`, `companyName`, and `role`. Resume and Note summaries each contain `id`, `title`, `companyName`, `role`, and absolute Notion `url`. The PDF summary contains `filename` and same-origin `downloadUrl`. The created Note and PDF are required.
- `already_created` uses `ok=true` and returns the existing Application and Resume. The Note and PDF are nullable because v1 does not repair incomplete historical artifacts through this route.
- `blocked` uses `ok=false`, `status=blocked`, and reports an ineligible Application, insufficient evidence, or readiness problem before artifact effects begin.
- `failed` uses `ok=false`, `status=failed`, and reports an attempted workflow that could not complete. It includes a `cleanup` summary with status `not_required`, `completed`, or `incomplete`, plus safe cleanup errors. Detailed concurrency, compensation, and residue rules remain owned by the recovery decision without changing this public shape.
- `GET /api/v1/resumes/{resumeId}/pdf` returns `application/pdf` with a safe `Content-Disposition` filename. It returns the common JSON technical error envelope with `404 pdf_not_found` when unavailable.
- `ResetDemoResponse` contains `ok=true`, result `reset`, and the common response fields. Reset changes demo state only; it does not return fixture records or local storage paths.

### Pagination contract

- Both queue routes accept optional `limit` and `cursor` query parameters. `limit` defaults to `5` and must be from `1` through `10` inclusive.
- Pagination is forward-only. The first page omits `cursor`; subsequent pages send the exact `nextCursor` returned by the backend.
- `pagination` always contains the accepted `limit`, nullable `nextCursor`, and `hasMore`. `nextCursor` is non-null if and only if `hasMore` is true.
- `queueCount` is the total number of currently eligible Applications at query evaluation, not the number on the current page.
- Cursors encode backend-owned ordering state and are URL-safe but intentionally undocumented. Frontends must not decode, modify, persist across sessions, or derive UI labels from them.
- A malformed, stale, or context-incompatible cursor returns `400 invalid_cursor`. Consumers respond by offering or automatically loading the first page; they do not retry the same cursor.
- After Application Analysis completes or repairs at least one item, both queue views reset to page one. After Resume Creation returns `created`, the Resume Creation Queue resets to page one. Manual refresh preserves current cursors only when they remain valid.

### Error and HTTP status boundary

- Expected product outcomes use route-specific HTTP `200` response unions, including blocked readiness, incomplete prepare review, duplicate capture, partial analysis completion, insufficient resume evidence, successful cleanup after a workflow failure, and duplicate Resume Creation.
- Technical failures use one `ApiErrorResponse` containing `ok=false`, an `error` object with `code`, `message`, and nullable `requestId`, plus `validationFailures` and `errors`. The `error.message` is safe for operator display; branching uses `error.code`.
- The locked technical status mapping is:

| Status | Error codes and use |
| --- | --- |
| `400` | `invalid_request`, `invalid_cursor` |
| `401` | `invalid_capture_token` for both missing and invalid capture tokens |
| `404` | `not_found`, `pdf_not_found`, `demo_not_active` |
| `405` | `method_not_allowed` |
| `409` | `conflict` only when a request cannot be represented as a safe typed idempotent or blocked outcome |
| `413` | `payload_too_large` |
| `415` | `unsupported_media_type` |
| `500` | `internal_error` for uncaught backend faults |

- FastAPI's default `422` validation body is replaced with `400 invalid_request` so all request validation uses the public envelope.
- Uncaught exceptions are logged with a correlation identifier but return only `internal_error`, a safe message, and the correlation identifier. Stack traces, raw exceptions, provider bodies, and secrets do not enter the response.
- `405` and other framework-generated errors are normalized to the common envelope before release.

### Authentication, origin, and CORS policy

- `POST /api/v1/applications/prepare` and `POST /api/v1/applications/confirm` require `X-Capture-Token`. Token comparison is constant-time, and missing and invalid values return the same `401 invalid_capture_token` response.
- Health is unprotected so the extension can test backend readiness without sending the token. Dashboard, operator settings, queue, analysis, Resume Creation, PDF, and demo-reset routes do not accept or require the capture token.
- Dashboard routes rely on the local same-origin deployment boundary in v1. CORS is not treated as authentication, and the server binds to a loopback interface by default under the runtime decision.
- Production dashboard calls are same-origin and require no CORS allowance. Development web origins and the installed `chrome-extension://` origin are explicit configuration entries.
- Wildcard origins, wildcard origin regexes, reflected origins, and credentialed CORS are forbidden. `allowCredentials` is false.
- Allowed CORS methods are `GET`, `POST`, and preflight `OPTIONS`. Allowed request headers are `Content-Type` and `X-Capture-Token`. No secret-bearing response headers are exposed.
- Requests without an `Origin` header, such as local CLI calls, remain possible; capture writes still require the token.
- No frontend route accepts Notion tokens, database IDs, DeepSeek keys, model names, prompts, or export paths as request data.

### Idempotency and retry surface

- V1 exposes no `Idempotency-Key` header and no client-generated operation ID. Semantic domain keys are the public idempotency surface.
- Application confirmation is repeatable by canonical Job URL and returns `already_captured` with the existing Application.
- Resume Creation is repeatable by Application and existing final Resume relation and returns `already_created` with discoverable existing outputs.
- Application Analysis repairs an existing readable Application Analysis whose final marker is incomplete, but a run request as a whole is not transport-idempotent.
- The generated transport performs no automatic retries for POST requests. UI retries are explicit operator actions after the prior outcome is known or safely classified.
- GET requests may be retried only for network failures using a bounded consumer policy. `400`, `401`, `404`, `409`, and `413` responses are never retried automatically.
- The concurrency and recovery decision may strengthen internal locking, journals, and compensation behind this surface, but it must not add generic client idempotency headers without reopening this contract.

### Generated TypeScript client boundary

- FastAPI's emitted OpenAPI 3 document is the source of truth. Handwritten TypeScript route payload types and handwritten generic fetch clients are removed as the final client is adopted.
- The accepted generator baseline is `@hey-api/openapi-ts` `0.99.0` with TypeScript `5.9.3`, a Fetch client, and pinned generation configuration. Dependency upgrades require regenerating and reviewing the contract artifact.
- Generation produces one logical package named `@merida/api-client` for both React consumers. Repository placement and workspace wiring are left to the runtime-topology decision.
- Stable operation IDs determine exported SDK function names. Named Pydantic schemas determine exported TypeScript type names. Python handler names, module moves, and router composition must not rename either accidentally.
- Generated code is read-only. Changes are made in the FastAPI models or generator configuration and then regenerated.
- The package owns URL/query encoding, JSON serialization, capture-token header support, response decoding, typed technical errors, and PDF binary response typing.
- The package does not own backend URL persistence, token storage, pending UI state, dirty-form state, queue refresh rules, notifications, or workflow orchestration.
- A dashboard-owned API adapter configures same-origin transport and exposes dashboard-shaped calls to the dashboard session. An extension-owned Capture adapter configures the stored backend base URL and injects `X-Capture-Token` only for the two protected operations.
- React components and sessions consume the adapters. They do not import generated transport internals throughout the component tree and do not call `fetch` directly.
- The generated client accepts an abort signal so consumers may cancel reads when a view is discarded. Long-running analysis and Resume Creation remain pending until their one final response; consumer timeouts must not cause automatic POST replay.

## Testing Decisions

- The single authoritative test seam is the configured FastAPI ASGI application in deterministic demo mode. Public-contract tests make HTTP requests through that seam and obtain the OpenAPI document from the same application.
- Good contract tests assert observable HTTP behavior: method and path, status, headers, JSON discriminants, safe fields, absence of secrets, pagination behavior, and binary PDF delivery. They do not assert router helper calls, internal Pydantic construction, workflow graph nodes, or adapter implementation details.
- Normalize and compare the emitted OpenAPI document against an accepted contract artifact. Any route removal, operation-ID change, request change, response change, required-field change, enum change, auth change, or content-type change requires intentional review.
- Generate `@merida/api-client` from the accepted OpenAPI document in verification, then typecheck the generated package and build both React consumers against it. A schema that generates but cannot be consumed is not accepted.
- Exercise every success and route-specific product-outcome variant through the public seam: ready and blocked health, prepared and needs-review capture, created and already-captured confirmation, empty and paginated queues, completed and partially failed analysis, created/already-created/blocked/failed Resume Creation, PDF success, and demo reset.
- Exercise every technical boundary: invalid JSON, invalid request fields, invalid cursor, missing and invalid token, oversized capture payload, unsupported media type, unknown resource, missing PDF, demo reset in real mode, normalized method error, conflict, and sanitized internal error.
- Assert privacy negatively: OpenAPI examples and live responses must not contain capture tokens, Notion secrets or database IDs, DeepSeek keys, prompts, full Job Content, Master Resume content, generated Resume bodies, raw model output, auth headers, or local paths.
- Assert CORS behavior for the configured extension origin, configured development origin, and a rejected arbitrary origin, including preflight for `X-Capture-Token`.
- Assert that operation IDs and named schema exports remain stable across generation.
- Assert that the dashboard adapter never sends `X-Capture-Token`, while the extension adapter sends it only for prepare and confirm.
- Assert that invalid cursors cause a first-page recovery and that successful mutations apply the specified queue reset rules at the consumer-session seam.
- Assert that generic transport code never automatically retries a POST. Repeat confirmation and Resume Creation explicitly to prove the domain idempotency outcomes.
- Existing prior art is the FastAPI public-contract suite, the external-runtime OpenAPI generation spike, deterministic demo adapter behavior, and the dashboard and side-panel session tests. Extend those test shapes instead of creating lower-level router mocks.
- Real Notion and demo stores still run the workflow-specific conformance suites settled by the module-seams decision. Those suites complement the HTTP contract but do not replace it.

## Out of Scope

- Python and TypeScript package roots, workspace tooling, generated-file location, build commands, and process lifecycle; the runtime-topology decision owns those details.
- Exact mapping between canonical Application models and legacy Notion databases, properties, page bodies, and relations; the Notion compatibility decision owns that mapping.
- Internal locking, durable journals, crash windows, compensation algorithms, cleanup residue persistence, and concurrent-operation policy; the concurrency and recovery decision owns those mechanics behind the locked public summary.
- Cloud deployment, remote authentication, user accounts, sessions, tenancy, OAuth, CSRF tokens, or internet-exposed operation.
- Generic CRUD for Applications, Job Postings, Resumes, or Notes.
- Quick Capture, batch Resume Creation, streamed workflow progress, WebSockets, SSE, NDJSON, webhooks, or background-job polling.
- Client-controlled model selection, prompts, provider credentials, Notion credentials, database IDs, or export paths.
- Missing-PDF repair, historical artifact repair, or arbitrary file browsing.
- Backward-compatible aliases for prototype routes or response shapes.

## Further Notes

- The API version identifies the wire contract, not the internal workflow or scoring-policy version. Matching and prompt policy versions may be recorded in durable artifacts without creating new route paths.
- The reviewed proposed route document should be reconciled to this issue before implementation tickets treat it as authoritative. In particular, it must adopt named response models, the common technical error envelope, `needs_review` prepare semantics, the fixed CORS policy, and the generated-client boundary.
- Demo mode and real mode use the same route inventory and schemas. Mode-specific availability appears as typed results, never as a second demo-only client contract.
- The recommended test seam was accepted from the user's instruction to proceed with the recommendations: use the FastAPI ASGI/OpenAPI boundary as the single highest seam, with generated-client compilation and consumer-adapter tests proving downstream usability.
- The implementation materializes the logical client package in the current checkout so both React consumers can use it. Its physical directory and workspace wiring remain provisional; issue 07 may move them without changing the package name, generated surface, or public API contract.

## Answer

The v1 public contract is locked to the thirteen `/api/v1` operations above,
named Pydantic request and response models, stable operation IDs, camelCase JSON,
typed product outcomes, one normalized technical error envelope, explicit local
CORS origins, capture-token protection only for prepare and confirm, opaque
forward cursors, domain-key idempotency without automatic POST retries, and one
final response per workflow. One generated `@merida/api-client` package serves
both React consumers through consumer-owned adapters, and the FastAPI
ASGI/OpenAPI boundary is the authoritative contract test seam.
