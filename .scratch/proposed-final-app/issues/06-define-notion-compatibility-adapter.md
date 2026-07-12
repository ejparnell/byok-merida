# Define the existing-Notion compatibility adapter contract

Type: grilling
Labels: ready-for-agent
Status: resolved
Blocked by: 01, 04
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

How should the canonical `Application` and `Job Posting` models map onto the unchanged prototype-era Notion databases, physical property names, page bodies, and relations, while keeping schema validation and Notion payloads out of feature interfaces and keeping the demo adapter behaviorally equivalent?

## Problem Statement

Merida's target modules and public API use canonical `Application`, `Job Posting`, `Application Analysis`, and `Role` language, but the existing Notion workspace still uses prototype-era physical names such as `Job Posting`, `Job Title`, `Application Date`, and relation properties named `Job Posting`. The current prototype also persists analysis under `Job Posting Analysis`, accepts both Notion database IDs and data-source IDs in relation metadata, and relies on inverse relation names for Resume and Note integrity.

The migration must preserve that workspace without renaming databases, properties, relations, or records. At the same time, physical Notion names, block payloads, pagination cursors, SDK responses, and provider errors must not leak into workflow modules or public API models. Without one compatibility contract, each workflow could translate the same page differently, demo mode could pass while real mode behaves differently, schema failures could become vague, and legacy analysis or relation data could become unreadable after cutover.

## Solution

Build one real-mode Notion compatibility adapter that implements the three workflow-owned store interfaces: `CaptureStore`, `ApplicationAnalysisStore`, and `ResumeCreationStore`. The adapter projects one existing Applications-database page into a canonical `Application` plus its one-to-one `Job Posting`; v1 does not create a second Job Posting record or relation. It translates canonical writes back into the existing physical properties and stable page-body sections.

The adapter validates only the schema capabilities required by the calling workflow, reports exact physical database and property names in safe validation failures, and returns typed domain values and store outcomes rather than Notion payloads. It reads both canonical `Application Analysis` bodies and legacy `Job Posting Analysis` bodies, writes only the canonical heading for new analysis, preserves the existing relation topology, and archives failed Notion drafts during compensation.

The real Notion adapter and demo adapter run the same behavioral conformance suite at each narrow store interface. Additional Notion-specific mapping tests prove physical names, schema rules, body parsing, relation targets, pagination translation, and safe error normalization. The shared suite tests domain behavior; demo mode is not required to emulate Notion JSON.

## User Stories

1. As the local operator, I want to use my existing Notion databases without renaming them, so that migration does not disrupt my workspace.
2. As the local operator, I want existing Application records preserved in place, so that links, history, and related materials remain intact.
3. As the local operator, I want a canonical Application to refer to the same pursuit record I already manage in Notion, so that the dashboard and Notion never disagree about identity.
4. As the local operator, I want the related Job Posting source information read from that same record, so that v1 does not create duplicate source pages.
5. As the local operator, I want newly captured Applications written with the existing physical property names, so that they remain compatible with my current views and formulas.
6. As the local operator, I want newly captured Applications to start at `To Apply`, so that they enter the intended pursuit workflow.
7. As the local operator, I want new capture records to remain unanalyzed with no Match Score, so that Merida does not claim work it has not performed.
8. As the local operator, I want the canonical Job URL used for duplicate detection, so that repeated capture returns the existing Application.
9. As the local operator, I want the exact Captured URL retained when the optional physical property exists, so that source-page provenance is not lost.
10. As the local operator, I want a missing optional Captured URL property to produce a warning rather than block capture, so that the prototype-compatible minimum remains usable.
11. As the local operator, I want Location to be optional in the capture form while still mapping to the existing rich-text property, so that remote or unspecified roles can be captured.
12. As the local operator, I want Capture Summary and Job Content to remain readable in Notion, so that the durable record is useful outside Merida.
13. As the local operator, I want long Job Content written safely within Notion's block limits, so that large postings do not create malformed requests.
14. As the local operator, I want incomplete capture writes reported as failures rather than completed records, so that I do not trust partial data.
15. As the local operator, I want only `To Apply` records with readable Job Content to appear in the Application Analysis Queue, so that every visible item can run now.
16. As the local operator, I want queue ordering based on the canonical Date Found value, so that work proceeds predictably even though Notion stores it as Application Date.
17. As the local operator, I want queue cursors to remain opaque backend values, so that Notion pagination mechanics never become a browser contract.
18. As the local operator, I want manually created pages without readable Job Content excluded from queues, so that invalid records remain manageable in Notion without breaking the whole dashboard.
19. As the local operator, I want existing `Job Posting Analysis` sections recognized, so that migrated records remain usable.
20. As the local operator, I want new analysis persisted under `Application Analysis`, so that future records use the canonical domain language.
21. As the local operator, I want a legacy analysis body to repair missing final properties without another model call, so that migration does not duplicate LLM work.
22. As the local operator, I want a persisted Match Score recovered exactly when present, so that repair does not change a completed result.
23. As the local operator, I want analysis content written before `Analyzed` and `Match Score`, so that a partial commit remains detectable and repairable.
24. As the local operator, I want both canonical and legacy analysis bodies handled deterministically, so that retries never combine unrelated sections.
25. As the local operator, I want Resume Creation to require readable Job Content and analysis from the selected Application, so that generation uses durable evidence.
26. As the local operator, I want exactly one readable Master Resume located through the existing `Name` property, so that evidence ownership is unambiguous.
27. As the local operator, I want the Master Resume body read recursively, so that nested Notion blocks do not silently discard evidence.
28. As the local operator, I want existing related Job-Specific Resumes detected through the current relations, so that retries return `already_created` without duplicate artifacts.
29. As the local operator, I want multiple related Resume records treated as an integrity problem, so that Merida never chooses an arbitrary completed artifact.
30. As the local operator, I want generated Resume drafts created without the Application relation, so that incomplete work does not look complete.
31. As the local operator, I want the final Resume-to-Application relation attached last, so that the existing relation remains the durable completion marker.
32. As the local operator, I want Resume Fit Analysis Notes related through the existing physical `Job Posting` and `Resume` properties, so that supporting evidence stays connected.
33. As the local operator, I want inverse `Resumes` and `Notes` relations validated, so that writes cannot silently target the wrong workspace topology.
34. As the local operator, I want failed draft Resumes and Notes archived, so that cleanup matches Notion's actual deletion model.
35. As the local operator, I want partial relation and artifact cleanup reported explicitly, so that I know when manual repair is needed.
36. As the local operator, I want schema failures to name the exact physical property I must fix, so that remediation in Notion is direct.
37. As the local operator, I want an unrelated missing optional management property not to block an LLM workflow, so that readiness stays workflow-specific.
38. As the local operator, I want unknown or malformed record values excluded safely, so that one bad page does not corrupt a whole batch.
39. As a workflow author, I want canonical Application and Job Posting values from the store, so that workflow code does not know Notion property names.
40. As a workflow author, I want semantic store operations rather than generic page CRUD, so that workflow rules remain visible in the owning module.
41. As a workflow author, I want body parsing hidden behind the adapter, so that analysis and resume logic never traverse raw blocks.
42. As a workflow author, I want schema capability results represented as typed validation failures, so that readiness does not depend on exception text.
43. As a workflow author, I want duplicate lookup and queue results expressed with canonical IDs, so that Notion page IDs remain opaque implementation values.
44. As a workflow author, I want Notion request failures normalized into stable store errors, so that raw provider responses do not become domain behavior.
45. As a backend developer, I want one translation authority shared by all three store implementations, so that physical fields are not mapped differently by each workflow.
46. As a backend developer, I want each workflow to receive only its own store interface, so that the shared adapter does not become a global Workspace interface.
47. As a backend developer, I want read and write DTOs owned by the adapter, so that Pydantic domain models do not import Notion SDK types.
48. As a backend developer, I want database IDs and credentials supplied only at composition time, so that workflows and HTTP responses never contain them.
49. As a backend developer, I want relation validation to accept Notion database-ID and data-source-ID representations, so that supported workspace metadata variations remain compatible.
50. As a backend developer, I want inverse relation names checked when Notion supplies them, so that the adapter catches a miswired relation before writing.
51. As a backend developer, I want absent inverse metadata handled explicitly, so that a missing optional API field is not mistaken for proof of an invalid schema.
52. As a backend developer, I want Notion result pagination fully consumed where eligibility requires body inspection, so that queue counts and pages are truthful.
53. As a backend developer, I want Notion cursors translated behind a Merida cursor boundary, so that storage changes do not break clients.
54. As a backend developer, I want deterministic tie-breaking by Application ID, so that pagination does not duplicate or skip equal sort values.
55. As a backend developer, I want rich-text, date, number, select, checkbox, URL, and relation decoding centralized, so that malformed property handling is consistent.
56. As a backend developer, I want new writes to omit unset Match Score rather than invent a zero, so that blank retains its domain meaning.
57. As a backend developer, I want body readers to select whole stable sections, so that they never merge Capture, analysis, or user-authored content accidentally.
58. As a backend developer, I want body writers to batch children within Notion request limits, so that transport constraints stay out of feature modules.
59. As a backend developer, I want unsafe Notion errors logged only with redaction and correlation context, so that credentials and private content remain private.
60. As a demo-mode author, I want the demo store to satisfy the same semantic contracts, so that portfolio walkthroughs exercise real workflow behavior.
61. As a demo-mode author, I want no requirement to manufacture Notion block payloads, so that demo mode remains a domain adapter rather than a Notion simulator.
62. As a test author, I want one conformance suite per workflow-owned store interface, so that real and demo behavior can be compared directly.
63. As a test author, I want Notion-specific mapping tests in addition to shared conformance tests, so that physical compatibility remains protected.
64. As a test author, I want fixtures for legacy and canonical analysis bodies, so that migration read compatibility cannot regress.
65. As a test author, I want fixtures for database-ID and data-source-ID relation targets, so that relation validation matches observed Notion responses.
66. As a test author, I want forbidden-output assertions, so that raw Notion payloads, credentials, database IDs, and private body content never cross the store seam.
67. As a migration implementer, I want the compatibility mapping versioned with parity fixtures, so that intentional schema changes require an explicit contract update.
68. As a migration implementer, I want real-mode cutover blocked until the Notion adapter passes conformance and parity suites, so that demo success is not mistaken for migration completion.

## Implementation Decisions

### Adapter ownership and authority

- One real-mode Notion compatibility adapter implements `CaptureStore`, `ApplicationAnalysisStore`, and `ResumeCreationStore`. It may share private codecs, schema inspection, block traversal, query, and error-normalization machinery internally.
- The FastAPI composition root constructs the adapter from backend-only settings and passes each workflow only its narrow store interface. Workflows never receive the combined concrete adapter type.
- The adapter is the only authority for translating between canonical domain values and the unchanged physical Notion schema. FastAPI routers, workflows, React consumers, generated clients, and model adapters do not contain fallback property-name mappings.
- The adapter exposes semantic operations required by the three workflows. It does not expose generic database query, page get, page update, block append, property patch, or archive-any-page operations.
- Notion credentials, configured database IDs, data-source IDs, raw blocks, raw properties, query filters, SDK response objects, and provider error bodies remain private to the adapter.
- The adapter uses feature-owned canonical values at its public boundary and private Notion read/write DTOs internally. Notion types do not appear in feature interfaces.

### Canonical identity and one-page projection

- In v1, one existing page in the physical Job Postings/Applications database projects into one canonical `Application` and its required one-to-one `Job Posting` source information.
- No separate Job Posting database, page, identifier, or relation is introduced. The Job Posting has no independently persisted public identity in v1; the Application ID is the opaque Notion page ID at the adapter boundary.
- The canonical Application owns pursuit state: ID, Notion URL, Application Status, Date Found, Analyzed state, Match Score, related Resume IDs, and related Note IDs.
- The canonical Job Posting owns source-opportunity data: Company Name, Role, Location, canonical Job URL, optional Captured URL, readable Job Content, and capture provenance.
- Public summaries flatten the canonical Job Posting display values onto the Application response as already locked by the public API contract. That flattening does not change internal ownership.
- Canonical Application title is derived as `{Role} at {Company Name}`. The physical title property stores the same value. Reads validate that the physical title is present but derive the public title from Company Name and Role so a stale display title cannot override canonical fields.
- IDs remain opaque non-empty strings. Workflows and clients may compare them but must not parse, prefix, or infer Notion URL structure from them.

### Physical-to-canonical property mapping

The existing physical schema remains authoritative for storage:

| Canonical value | Physical database and property | Physical type | Translation rule |
| --- | --- | --- | --- |
| Application ID | Applications page ID | page identity | Return as an opaque string. |
| Application URL | Applications page URL | page metadata | Return only the safe absolute Notion page URL. |
| Application title | `Job Posting` | title | Write `{Role} at {Company Name}`; require a readable title on existing pages but derive the canonical display title. |
| Company Name | `Company Name` | rich text | Trim and require for capture and queue eligibility. |
| Role | `Job Title` | rich text | Translate to canonical `role`; do not require or create a physical `Role` property. |
| Job URL | `Job URL` | URL | Store the canonicalized URL and use it for duplicate lookup. |
| Captured URL | `Captured URL` | URL | Optional physical property; write the exact source URL when present. |
| Location | `Location` | rich text | Physical property remains required by the compatibility schema; its value may be empty and maps to canonical `null`. |
| Date Found | `Application Date` | date | Write capture date and translate to canonical `dateFound`; do not require or create `Date Found`. |
| Application Status | `Application Status` | select | Capture writes `To Apply`; queues include only exactly `To Apply`. |
| Analyzed | `Analyzed` | checkbox | Capture writes `false`; analysis finalization writes `true`. |
| Match Score | `Match Score` | number | Read as integer `0..100` or `null`; capture omits it; analysis finalization writes it. |
| Related Resume IDs | `Resumes` | relation | Read relation IDs; the inverse on Resumes must be `Job Posting`. |
| Related Note IDs | `Notes` | relation | Read relation IDs; the inverse on Notes must be `Job Posting`. |

- The physical database may still be described to the operator as the Applications database, but validation failures identify the exact physical property names above.
- Optional management properties such as Work Type, Employment Type, Salary Range, Application Deadline, Next Step Date, and Last Contacted are neither required nor translated by workflow stores in v1.
- The `Application Status` schema must contain `To Apply`, because Capture writes it. Known non-queue values are `Applied`, `Rejected`, `Not Interested`, and `Archived`. Extra select options produce a warning rather than a global block; records with unknown values are ineligible and receive a safe per-record diagnostic when directly selected.
- Missing or wrong-typed required physical properties produce `workspace_schema` validation failures. A value-level problem on one page is a record-read or eligibility failure, not a claim that the database schema is invalid.
- Empty rich-text arrays map to `null` for optional values and to a typed record-data failure for required values. Empty strings are not passed through as valid canonical required fields.

### Resume and Note physical mappings

- The existing Resumes database keeps physical `Name` as its title property and physical `Job Posting` as its Application relation. The inverse relation in the Applications database remains `Resumes`.
- The existing Notes database keeps physical `Name` as its title property, physical `Job Posting` as its Application relation, and physical `Resume` as its Resume relation. Their inverse relations remain `Notes`.
- A Master Resume is an active Resumes page whose physical `Name` equals `Master Resume`. It must not have a Job Posting relation. Resume Creation requires exactly one readable active match.
- A Job-Specific Resume stores `{Role} at {Company Name}` in physical `Name`. It is initially created without the physical `Job Posting` relation and receives that relation only as the final completion effect.
- A Resume Fit Analysis Note stores `Resume Fit Analysis - {Role} at {Company Name}` in physical `Name` and relates to both the Application and the unlinked Resume draft through the physical relation names.
- The adapter treats the Applications `Resumes` relation and the Resume `Job Posting` relation as two views of the same Notion relation. It does not patch both sides independently when Notion's dual relation maintains the inverse.
- One related active Job-Specific Resume means Resume Creation returns the existing artifact. More than one active related Job-Specific Resume is an integrity block and is never resolved by choosing the first relation entry.
- Archived Resume and Note pages are not returned as active artifacts. Cleanup uses Notion archival and reports `Archived`; it never claims that a page was hard-deleted.

### Workflow-scoped schema capabilities

- Schema validation is capability-based. Each workflow asks for the exact database properties, types, writable select option, relation targets, and inverse names it needs; there is no single all-or-nothing global workspace validator.
- Capture readiness validates the Applications properties needed to find duplicates and create a complete capture record, plus body-write access. Missing optional Captured URL produces a warning. Resume and Notes relations do not block Capture.
- Application Analysis readiness validates the Applications properties needed for eligible queue reads, Job Content reads, analysis body writes, Match Score finalization, and Analyzed repair. Its separate workflow readiness may additionally require the Resumes database and readable Master Resume evidence for deterministic matching, but that requirement is not folded into the Applications schema codec.
- Resume Creation readiness validates the Applications, Resumes, and Notes properties and all required relation pairs, plus readable page-body access. Capture-only optional properties do not block it.
- Schema inspection accepts relation targets represented by a configured database ID, the database object's ID, or one of its returned data-source IDs.
- When a relation supplies a data-source ID but the database response provides no data-source IDs to compare, strict target comparison is skipped with a warning rather than reported as proven valid.
- When Notion supplies dual-relation inverse metadata, the inverse name must match the exact physical contract. Missing inverse metadata produces a warning when the target is otherwise compatible; a conflicting inverse name is an error.
- Validation results contain canonical database labels (`applications`, `resumes`, or `notes`), exact physical property names, a safe message, and warning/error severity internally. Public readiness maps errors to `workspace_schema` failures and may include safe warnings without exposing raw schema payloads.
- A workflow write rechecks or uses a short-lived validated schema capability before effects begin. A stale startup health result is not permanent authorization to write after the workspace changes.

### CaptureStore contract

- `CaptureStore` supports four semantic capabilities: validate Capture workspace readiness, find an Application by canonical Job URL, create a new Application from a confirmed canonical draft and capture metadata, and return a safe Application summary.
- URL canonicalization and confirm-time field validation remain owned by Application Capture. The store receives a canonical Job URL and does not invent a second normalization policy.
- Duplicate lookup queries physical `Job URL` for exact equality and returns either one canonical Application summary or no match. Multiple active matches are a workspace data conflict, not `already_captured` with an arbitrary page.
- Creation writes physical properties and the Capture Summary plus Job Content body. It sets `Job Posting`, `Company Name`, `Job Title`, `Job URL`, optional `Captured URL`, `Location`, `Application Date`, `Application Status=To Apply`, and `Analyzed=false`. It omits Match Score instead of writing zero or null.
- Capture Summary persists the canonical source URL, capture timestamp, optional exact Captured URL, and safe parsing notes. Job Content persists cleaned readable text, not raw DOM or a full Notion payload.
- Property text and body content are split into legal rich-text and child-block sizes by the adapter. Transport chunking is not observable at the store interface.
- A Notion create or append failure returns a typed store failure. Whether a partially created capture page is automatically archived is deferred to the concurrency and recovery decision; it must never be returned as a successful captured Application.

### ApplicationAnalysisStore contract

- `ApplicationAnalysisStore` supports five semantic capabilities: validate analysis workspace readiness, return an eligible queue page, load one Application analysis input, append a validated Application Analysis document, and finalize or repair analysis properties.
- An eligible new-analysis record has Application Status `To Apply`, `Analyzed=false`, required display properties, and readable Job Content. A repair candidate has those properties plus a readable canonical or legacy analysis body even when no new model call is needed.
- Because Notion cannot filter page-body readability in a database query, the adapter may over-fetch physical candidates, read bodies, exclude invalid records, and continue until it can return a truthful eligible page or reaches the end. Queue count represents eligible records after body inspection, not raw query matches.
- Analysis queue order is Application Date ascending, then opaque Application ID ascending. Null or invalid Application Date makes a record ineligible and yields a safe record diagnostic rather than unstable pagination.
- Store cursors are Merida-owned opaque cursor values bound to the workflow, sort contract, and eligibility snapshot. Raw Notion `next_cursor` values never cross the store or HTTP boundary. Cursor encoding and stale-snapshot policy remain shared backend pagination infrastructure.
- Loading analysis input returns canonical Application metadata, Job Content, analyzed state, Match Score, and at most one selected persisted analysis document. It does not return raw blocks.
- Appending a new analysis writes one top-level `Application Analysis` section with stable `Summary`, `Match Score`, and `Skill Signals` subsections. New code never writes `Job Posting Analysis`.
- Finalization is a separate semantic operation after the body append. It writes Match Score and `Analyzed=true` together as the final property commit.
- Repair reads an existing selected analysis document, recovers its exact persisted Match Score when available, and updates final properties without appending another body or calling the model. Legacy bodies without a persisted score may use the workflow's deterministic recomputation rule; if recovery is impossible, the adapter supports `Analyzed=true` with Match Score left empty.

### Page-body compatibility and section selection

- Capture body readers recognize the top-level `Capture Summary` and `Job Content` headings. Job Content includes readable blocks after its heading until the next top-level section heading.
- Analysis body readers recognize canonical `Application Analysis` and legacy `Job Posting Analysis` as alternative top-level analysis headings.
- A complete canonical analysis requires readable Summary and Skill Signals subsections; new canonical bodies also require a readable Match Score subsection. A legacy body may omit Match Score and still be eligible for property repair under the documented recovery rules.
- When canonical and legacy analysis sections both exist, the adapter selects the last complete canonical section. If none is complete, it selects the last complete legacy section. It never concatenates fields across sections.
- When multiple sections of one recognized kind exist, the last complete section wins because Notion appends blocks chronologically. Earlier sections remain untouched compatibility history.
- An incomplete trailing section does not hide an earlier complete section. If no complete recognized section exists, the record has no readable Application Analysis.
- The adapter reads all paginated child blocks needed for a stable section and supports recursive traversal where Notion containers can hold meaningful Resume evidence. It enforces bounded depth and total-block safeguards and returns a typed unreadable-content failure when those safeguards are exceeded.
- Block codecs accept only the supported readable block types. Unsupported blocks may be skipped with diagnostics; they are never serialized wholesale into prompts or domain models.
- User-authored content outside recognized stable sections remains untouched and is not included in workflow inputs merely because it is present on the page.

### ResumeCreationStore contract

- `ResumeCreationStore` supports semantic capabilities for readiness, eligible queue paging, loading one Application creation input, finding existing completed artifacts, loading the Master Resume document, creating and archiving an unlinked Resume draft, creating and archiving a Resume Fit Analysis Note, and attaching the final Resume relation.
- Resume Creation Queue eligibility requires Application Status `To Apply`, `Analyzed=true`, readable Company Name and Role, readable Job Content, a readable selected analysis section, a valid Match Score, and no active related Job-Specific Resume.
- Resume queue order is Match Score descending, Application Date ascending, then opaque Application ID ascending. Queue pagination follows the same Merida-owned cursor rule as Application Analysis.
- Direct creation re-reads the Application and all relevant relations rather than trusting a prior queue item. A stale or ineligible Application returns a typed block before artifact effects begin.
- The existing-Resume check occurs before Master Resume, model, Note, PDF, or new Resume work. It returns canonical safe artifact summaries without raw relations.
- Master Resume loading returns one canonical Resume document with ordered, readable block values and source structure. It does not return Notion blocks to Resume Creation.
- The adapter creates a Resume page with physical `Name` and no physical `Job Posting` relation, appends the validated employer-facing Resume document, and returns a canonical draft reference.
- The adapter creates the Resume Fit Analysis Note with physical `Name`, `Job Posting`, and `Resume` relations and appends the validated Note document.
- The artifact committer, not the adapter, controls external-effect order. The adapter's final attachment operation patches the Resume physical `Job Posting` relation only after Resume, Note, and PDF effects have succeeded.
- Compensation operations are deliberately narrow: clear a partial final relation if necessary, archive the created Note, and archive the created Resume. General record deletion or arbitrary relation editing is not part of the store interface.
- PDF creation and removal remain behind the PDF/filesystem adapter, not the Notion adapter. The Notion adapter returns IDs and Notion URLs needed to assemble the public artifact summary but never local paths.

### Notion error and privacy boundary

- Provider authentication, permission, not-found, rate-limit, timeout, conflict, validation, and unexpected failures are normalized into internal typed store errors with safe messages and retryability metadata where needed.
- Raw Notion response bodies and exception messages are never returned directly through workflows or HTTP. Safe schema failures preserve exact physical property names because those names are required for operator remediation.
- Logs may include workflow name, semantic operation, correlation ID, safe database label, page ID when necessary for local repair, Notion status/code, and retry classification. They do not include credentials, authorization headers, database IDs, full properties, Job Content, Master Resume content, analysis bodies, Resume bodies, Note bodies, or request payloads.
- Read and write methods redact private content before structured error reporting. A correlation ID connects the safe public error to local diagnostics.
- The adapter never returns Notion tokens, database IDs, data-source IDs, physical schema payloads, full private content, or archive requests through public API response models.

### Demo behavioral equivalence

- The demo adapter implements the same three workflow-owned store interfaces and returns the same canonical domain values, typed outcomes, ordering, eligibility, duplicate, idempotency, and cleanup semantics.
- Demo mode uses fictional canonical fixtures and local mutable state. It does not implement physical Notion property names, raw block shapes, database/data-source relation metadata, or Notion error payloads.
- Shared conformance tests are parameterized over the real Notion adapter with deterministic HTTP recordings and the demo adapter with deterministic local state.
- Notion-only compatibility tests supplement rather than replace shared conformance. Passing demo tests alone is insufficient to enable real mode.
- Real-mode readiness remains blocked until schema, adapter conformance, parity, privacy, and cleanup suites pass against the compatibility implementation.

## Testing Decisions

- The highest test seam is each public workflow-owned store interface. The same behavioral contract suite runs against the real Notion adapter and demo adapter for `CaptureStore`, `ApplicationAnalysisStore`, and `ResumeCreationStore`.
- Good conformance tests assert canonical inputs, canonical outputs, semantic durable effects, ordering, idempotency, eligibility, pagination behavior, cleanup residue, and forbidden outputs. They do not assert private helper calls or raw Notion SDK object identity.
- CaptureStore conformance covers readiness, exact canonical-URL lookup, no match, duplicate conflict, successful creation defaults, optional Location, optional Captured URL, readable Capture Summary and Job Content effects, and unsuccessful partial creation.
- ApplicationAnalysisStore conformance covers eligible-only queue paging, body-read filtering, deterministic order, stale cursors, canonical input loading, legacy repair loading, canonical analysis append, body-before-properties, exact Match Score finalization, and repair without append.
- ResumeCreationStore conformance covers eligible-only queue paging, direct revalidation, exactly one Master Resume, existing artifact discovery, multiple-Resume integrity failure, unlinked draft creation, Note relations, relation-last attachment, archival compensation, and safe artifact references.
- Notion mapping tests use representative redacted database, page, property, block, and query fixtures. They prove every physical-to-canonical mapping and canonical-to-physical write listed in this spec.
- Schema tests cover missing properties, wrong property types, missing `To Apply`, optional Captured URL absence, extra Application Status options, database-ID relation targets, data-source-ID targets, unavailable comparison metadata, correct inverse names, conflicting inverse names, and workflow-scoped validation.
- Body codec tests cover Capture Summary, Job Content boundaries, canonical analysis, legacy analysis, missing legacy score, both heading kinds, repeated headings, incomplete trailing sections, unsupported blocks, pagination, recursive Master Resume children, maximum depth, total-block bounds, and no cross-section merging.
- Query tests prove that physical candidates without readable Job Content or analysis do not inflate queue pages or queue counts, and that the adapter continues scanning after excluded records.
- Pagination tests prove stable ordering, ID tie-breaking, context-bound cursors, stale cursor rejection, no raw Notion cursor exposure, no duplicate items, and no skipped eligible items across pages.
- Write-intent tests assert normalized semantic Notion requests rather than full brittle HTTP snapshots. Exact property names, property types, relation IDs, stable headings, omitted Match Score on Capture, and relation-last Resume attachment are contract assertions.
- Error-boundary tests inject representative Notion authentication, permission, validation, rate-limit, timeout, not-found, conflict, malformed payload, and unexpected failures. They assert typed normalization, safe messages, correlation context, and redaction.
- Privacy tests inspect all store results, workflow results, HTTP responses, structured logs, and demo state boundaries for forbidden credentials, database IDs, raw payloads, full Job Content, Master Resume content, generated Resume bodies, Note bodies, and local PDF paths.
- Existing prototype Notion client tests provide prior art for required property validation, optional Captured URL warnings, Capture Defaults, canonical URL lookup, block batching, recursive Resume reads, relation targets, inverse names, unlinked Resume creation, final attachment, and archival.
- Existing parity scenarios provide prior art for stable body sections, legacy `Job Posting Analysis` recognition, body-first analysis persistence, repair without another model call, relation compatibility, semantic artifact effects, idempotency, and cleanup residue.
- Existing target public-contract tests remain responsible for HTTP validation, auth, response unions, and technical error envelopes. They do not duplicate Notion mapping behavior.
- Contract fixtures use fictional content and deterministic IDs, dates, cursors, and Notion responses. No private workspace export or real resume content is checked into the repository.
- Completion requires a mapping coverage table showing every canonical field, physical property, stable body section, relation pair, schema capability, store operation, provider error class, and shared conformance behavior has at least one test.

## Out of Scope

- Renaming, creating, deleting, or migrating existing Notion databases, properties, relations, select options, pages, or historical content.
- Introducing a separate physical Job Posting record or relation in v1.
- Generic Notion CRUD, a global Workspace interface, a repository-wide ORM, or a reusable transaction framework.
- Changing the locked public HTTP routes, generated-client contracts, response DTOs, auth policy, or CORS policy.
- Changing Application Analysis, Matching, Resume generation, evidence-validation, or LLM prompt behavior.
- Choosing final Python package roots, dependency versions, workspace tooling, runtime process topology, or deployment packaging.
- Settling cross-process locking, durable idempotency journals, process-crash recovery, or the final compensation state machine beyond the adapter operations required by that decision.
- Defining demo reset, persistence-location, screenshot, or portfolio acceptance beyond store behavioral equivalence.
- Editing or managing Applications, Resumes, or Notes from the dashboard.
- Supporting arbitrary Notes, batch Resume Creation, missing-PDF repair, cloud Notion webhooks, remote sync, multi-user workspaces, or schema auto-repair.
- Preserving prototype route names, streamed transport, JavaScript module layout, raw Notion payload shapes, or exact low-level request call counts.
- Hard-deleting Notion pages during compensation.

## Further Notes

- The existing physical workspace is intentionally allowed to retain Job Posting language while the target domain and operator workflows use Application language. The adapter is the explicit anti-corruption layer between those vocabularies.
- `Application Analysis` is the only heading written by the target. `Job Posting Analysis` is a permanent v1 read-compatibility alias, not a second canonical workflow name.
- The reviewed proposed Notion documentation currently shows canonical property names. This decision requires its later reconciliation to distinguish canonical domain fields from unchanged physical Notion properties.
- The current target demo store combines workflow behavior and persistence behind broad methods. Implementation may split those methods to satisfy the semantic store operations above, but it must preserve the already locked public API behavior.
- This decision does not enable real mode by itself. Real-mode cutover still depends on the concurrency/recovery, runtime-topology, demo-acceptance, and migration-roadmap decisions plus executable parity.

## Answer

The Notion compatibility boundary is one real adapter implementing three narrow workflow-owned store interfaces. One unchanged physical Applications/Job Postings page projects into a canonical Application and its one-to-one Job Posting; no second source record is created. The adapter preserves legacy property and relation names, reads both legacy and canonical analysis bodies, writes canonical `Application Analysis`, validates workflow-specific schema capabilities, translates Notion pagination and failures into backend-owned types, and keeps all Notion payloads out of feature and API interfaces.

The accepted testing seam is the public contract of each narrow store interface. The real Notion adapter and demo adapter must pass the same Capture, Application Analysis, and Resume Creation conformance suites, with additional Notion-specific mapping, schema, relation, body-codec, privacy, and error-normalization tests required before real-mode cutover.

Implementation coverage is recorded in [Notion Compatibility Coverage](../assets/notion-compatibility-coverage.md).
