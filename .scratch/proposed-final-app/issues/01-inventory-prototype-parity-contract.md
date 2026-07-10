# Inventory the prototype behaviors that define migration parity

Type: task
Status: resolved
Blocked by: none
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

Which observable prototype behaviors must become versioned parity fixtures for Capture, Application Analysis, Resume Creation, Notion persistence, evidence validation, artifact creation, idempotency, and failure cleanup, and which prototype behaviors are intentionally superseded by the reviewed final-app contracts?

## Problem Statement

Merida has a working prototype and a reviewed final-app design, but it does not yet have one authoritative, versioned inventory that distinguishes behavior the migration must preserve from behavior the final app intentionally replaces. Without that contract, implementation agents could preserve incidental Node, HTML, route, streaming, or Python-sidecar details while accidentally regressing the outcomes that matter: readable capture, evidence-backed analysis, truthful resume generation, compatible Notion effects, idempotent retries, durable artifacts, and complete failure cleanup.

The migration needs an executable behavioral reference before the prototype is replaced. That reference must describe externally observable workflow results and durable effects without turning the prototype's internal module layout or legacy transport into permanent architecture.

## Solution

Create a classified, versioned parity corpus for Capture, Application Analysis, and Resume Creation. Exercise each scenario at the public workflow-module boundary with deterministic recording adapters. Record the typed domain outcome, normalized workspace and artifact effects, ordered external-effect trace, dependency call counts, cleanup residue, and forbidden effects.

Use a narrow companion contract for extension-side Capture Evidence normalization because evidence collection occurs before the backend workflow boundary. Keep legacy Notion property names, relations, and persisted body structures as compatibility evidence while expressing expected behavior with the canonical Application domain language.

Every inventoried behavior must be classified as `parity_required`, `superseded`, `target_addition`, `known_defect`, or `deferred`. The resulting inventory is the migration gate: final-app implementations must satisfy all `parity_required` and `target_addition` scenarios, must not accidentally restore `known_defect` behavior, and must follow the reviewed replacement for `superseded` behavior.

## User Stories

1. As a Merida operator, I want captured Applications to retain readable Job Content, so that later LLM workflows have trustworthy source material.
2. As a Merida operator, I want review-first Capture to parse without writing to my workspace, so that I can correct important fields before creation.
3. As a Merida operator, I want Capture to prefer text I deliberately selected, so that the most relevant Source Page evidence drives parsing.
4. As a Merida operator, I want Capture Evidence from readable frames and metadata to be normalized consistently, so that complex job pages remain capturable.
5. As a Merida operator, I want tracking noise removed from a canonical Job URL while preserving the Captured URL as evidence, so that duplicate detection is reliable without losing provenance.
6. As a Merida operator, I want a duplicate Capture to return the existing Application as a successful result, so that retries never create duplicate records.
7. As a Merida operator, I want weak or incomplete Capture results to require review, so that Merida does not create low-quality Applications silently.
8. As a Merida operator, I want missing readable Job Content to block creation, so that unusable Applications do not enter downstream queues.
9. As a Merida operator, I want schema failures to identify the affected database and property, so that I can correct my Notion workspace safely.
10. As a Merida operator, I want newly captured Applications to start at `To Apply` without an analysis marker or Match Score, so that Capture does not claim later workflow work has happened.
11. As a Merida operator, I want captured pages to retain stable Capture Summary and Job Content sections, so that the record remains readable and machine-processable.
12. As a Merida operator, I want only eligible Applications to enter the Application Analysis Queue, so that the dashboard presents work that can run now.
13. As a Merida operator, I want Application Analysis batches to be bounded and sequential, so that local provider and workspace usage remains predictable.
14. As a Merida operator, I want one failed Application to leave the rest of an analysis batch running, so that one bad record does not waste the batch.
15. As a Merida operator, I want every Application Analysis summary to contain exactly three evidence-backed sentences, so that the result is compact and consistent.
16. As a Merida operator, I want every Skill Signal tied to readable Job Content, so that unsupported model output cannot become durable analysis.
17. As a Merida operator, I want generic traits rejected unless the Application ties them to concrete work, so that analysis stays useful and specific.
18. As a Merida operator, I want duplicate normalized Skill Signals merged, so that repeated model wording does not distort the analysis.
19. As a Merida operator, I want Match Score calculated deterministically rather than by the LLM, so that the same validated evidence produces the same score.
20. As a Merida operator, I want Application Analysis written to the body before final properties are committed, so that a partial write can be detected and repaired.
21. As a Merida operator, I want an existing readable analysis body to repair missing properties without another model call, so that retries are safe and inexpensive.
22. As a Merida operator, I want exact persisted Match Score recovery when possible, so that repair does not silently change a completed analysis.
23. As a Merida operator, I want Resume Creation to revalidate the selected Application, so that stale dashboard state cannot create an invalid Resume.
24. As a Merida operator, I want an existing Resume Attachment to return `already_created`, so that repeated requests cannot create duplicate application materials.
25. As a Merida operator, I want Resume Creation to require readable Job Content and Application Analysis, so that generation always has the agreed source inputs.
26. As a Merida operator, I want Resume Creation to require exactly one readable Master Resume, so that the evidence source is unambiguous.
27. As a Merida operator, I want insufficient Master Resume evidence to block before any artifact is created, so that failed generation leaves no cleanup burden.
28. As a Merida operator, I want Fit Requirements validated against Job Content, so that Application Analysis cannot override the source opportunity.
29. As a Merida operator, I want only direct or adjacent evidence to support targeted resume claims, so that weak overlap cannot become an invented qualification.
30. As a Merida operator, I want every generated bullet connected to valid Resume Claim Traces, so that each claim remains auditable.
31. As a Merida operator, I want evidence to remain within its source role, so that Merida never transfers accomplishments between employers or positions.
32. As a Merida operator, I want every Master Resume work-experience role preserved in its original order, so that tailoring does not rewrite my chronology.
33. As a Merida operator, I want each preserved role to contain five to seven truthful bullets or fail before writes, so that every generated Resume is application-ready.
34. As a Merida operator, I want education, certifications, volunteer work, contact details, and other non-work sections preserved unchanged, so that the LLM cannot embellish them.
35. As a Merida operator, I want the Notion Resume and PDF rendered from the same validated Resume Document, so that the two employer-facing artifacts agree.
36. As a Merida operator, I want Resume Fit Analysis stored in a related Note rather than the employer-facing Resume, so that supporting evidence remains durable without polluting the document.
37. As a Merida operator, I want the final Resume-to-Application relation attached last, so that the Resume Attachment remains the durable completion marker.
38. As a Merida operator, I want failures during artifact commit compensated in reverse order, so that partial relations, PDFs, Notes, and Resume drafts do not appear complete.
39. As a Merida operator, I want cleanup results reported explicitly, so that I know when manual Notion cleanup may still be required.
40. As a Merida operator, I want private Job Content, Master Resume content, prompts, credentials, and raw model responses excluded from normal logs and browser responses, so that local workflow data remains private.
41. As a migration implementer, I want each fixture to have a stable identifier and classification, so that I can trace every migration decision to an explicit contract.
42. As a migration implementer, I want deterministic clocks, identifiers, model outputs, and adapter responses, so that parity failures are reproducible.
43. As a migration implementer, I want semantic workspace effects instead of raw Notion HTTP snapshots, so that the Notion adapter can change without hiding a domain regression.
44. As a migration implementer, I want ordered effect traces for commit and compensation scenarios, so that a superficially correct final state cannot hide unsafe write ordering.
45. As a migration implementer, I want forbidden effects recorded alongside expected effects, so that tests prove blocked and idempotent outcomes performed no writes or model calls.
46. As a migration implementer, I want scoring-policy and normalization-dictionary versions recorded in relevant fixtures, so that intentional scoring changes cannot masquerade as refactors.
47. As a Notion adapter author, I want legacy physical property and relation names captured separately from canonical domain fields, so that existing user data survives the migration unchanged.
48. As a Notion adapter author, I want existing Job Posting Analysis content recognized as compatibility data, so that old records remain readable and repairable after Application Analysis becomes the canonical workflow term.
49. As a reviewer, I want every preserved behavior linked to prototype evidence and every replacement linked to a reviewed final-app contract, so that fixture authority is auditable.
50. As a reviewer, I want known prototype defects classified explicitly, so that migration parity does not require reproducing broken behavior.
51. As a reviewer, I want legacy transport and UI details marked as superseded, so that parity does not freeze backend-rendered pages, old paths, or NDJSON.
52. As a future implementation agent, I want deferred decisions routed to their owning Wayfinder tickets, so that this inventory does not silently settle module, API, adapter, recovery, demo, or migration-roadmap design.

## Implementation Decisions

- This ticket produces the classified fixture inventory and executable prototype observations. It does not implement the FastAPI backend, React dashboard, React extension, LangGraph workflows, or migration.
- Current executable behavior is established by the working prototype and focused tests. Intentional replacements and additions are established by the reviewed final-app route, dashboard, extension, Notion schema, and AI workflow contracts. When those authorities conflict, the inventory records the conflict and classification instead of silently choosing one.
- The inventory uses canonical domain language: an Application is the pursuit record; its one-to-one Job Posting is the source opportunity and Job Content. Legacy Notion names and legacy Job Posting Analysis headings are recorded as physical compatibility details rather than preferred domain vocabulary.
- Every entry is classified as one of:
  - `parity_required`: an observable prototype outcome or safety property the final app must preserve.
  - `superseded`: prototype behavior intentionally replaced by a reviewed final-app contract.
  - `target_addition`: reviewed final-app behavior with no complete prototype precedent that must be present at cutover.
  - `known_defect`: observed broken or contradictory prototype behavior that must not become a compatibility requirement.
  - `deferred`: a related decision owned by another ticket and not settled by this inventory.
- The primary parity seam is one runtime-neutral scenario corpus over the public Capture, Application Analysis, and Resume Creation workflow interfaces. Separate production workflows remain independent; the shared test harness standardizes scenario inputs and observations without creating a shared production workflow abstraction.
- Capture Evidence normalization uses one narrow supporting seam before the backend workflow boundary. It covers active-tab and frame evidence normalization, selected-text precedence, readable-content fallback, metadata use, size limits, and canonical-versus-captured URL behavior.
- Each scenario records a stable fixture ID, fixture schema version, classification, workflow, authority source, canonical initial workspace state, action, deterministic dependency outputs, expected typed outcome, normalized durable effects, ordered external-effect trace, forbidden effects, cleanup residue, and applicable scoring-policy or normalization-dictionary version.
- Dynamic identifiers, timestamps, Notion URLs, provider request IDs, and filesystem roots are normalized unless their exact value is the behavior under test. Model prose and PDF bytes are not golden snapshots.
- Capture parity fixtures cover selected-text and multi-frame evidence, parse-only no-write behavior, successful high-confidence creation, `needs_review`, missing Job URL, missing readable Job Content, invalid schema, canonical duplicate detection, reviewed confirmation, Capture Defaults, and stable Capture Summary and Job Content persistence.
- The inventory records review-first **Fill Form** as the primary target interaction. Optional Quick Capture is not required for v1 parity, and the prototype's contradictory direct-capture documentation is not treated as executable UI authority.
- Application Analysis parity fixtures cover eligible queue selection, sequential bounded processing, failure isolation, three-sentence summaries, evidence-backed Skill Signals, generic-signal rejection, duplicate normalization, body-first persistence, property-final commit, partial-write detection, and repair without an additional LLM call.
- The reviewed `1` through `10` batch range supersedes the prototype's `1` through `25` range. A single final HTTP response supersedes NDJSON progress streaming; pending presentation belongs to the dashboard interaction contract.
- Readable Job Content is part of target queue eligibility. The prototype behavior in which an unreadable queued record fails only after a run begins is superseded by the eligible-only queue contract.
- Deterministic Match Score calculation, persistence in both the Application Analysis body and property, and exact score recovery are `target_addition` behaviors. The LLM must not supply the final Match Score.
- Resume Creation parity fixtures cover eligibility revalidation, early existing-Resume detection, readable source requirements, exactly one Master Resume, evidence extraction, deterministic matching and Fit Score, the generation gate, claim-trace validation, same-role evidence ownership, role chronology, five-to-seven bullet completion, employer-facing content, fit-analysis Note creation, PDF creation, final relation commit, idempotent retry, and cleanup at every commit stage.
- The prototype's fixed Elizabeth-specific role template is superseded. The target parses identity, work-experience roles, chronology, evidence items, and non-work sections from the Master Resume. Preserving non-work sections unchanged is a `target_addition` requirement.
- The prototype's `already_exists` Resume outcome is normalized to the reviewed `already_created` result.
- The target canonical Resume Document is the single source for Notion Resume and PDF rendering. Exact PDF layout, byte sequence, legacy export directory, Elizabeth-specific filename, and exposure of a local path are superseded by a backend-owned artifact and download contract.
- Successful Resume Creation commits artifacts before relations and attaches the Resume-to-Application relation last. Failure compensation clears partial relations, removes a written PDF, archives the draft Note, and archives the draft Resume in reverse order. Cleanup observations use `Archived`, not `Deleted`, for Notion pages.
- Existing physical Notion databases, property names, relations, and records are not renamed or migrated by this ticket. Fixtures capture both legacy physical data and canonical domain projections; the exact adapter mapping remains owned by the Notion compatibility ticket.
- Existing persisted Job Posting Analysis bodies must remain readable and repairable. Whether new writes use a different stable heading and how both shapes are translated remains an adapter/API compatibility decision, not an implicit rename in this inventory.
- Relation compatibility fixtures include accepted Notion relation target representations and inverse relation validation because those behaviors protect the existing workspace contract.
- The inventory marks backend-rendered `/analysis` and `/resumes` pages, legacy route names, NDJSON transport, the Node-to-Python runtime split, internal module layout, prompt character slicing, private content previews in logs, exact model prose, incidental call structure, and old response field names as `superseded` rather than parity requirements.
- The inventory records the current side-panel result-rendering defect and contradictory direct-capture documentation as `known_defect`; it preserves the intended review-first outcome states, not the broken presentation.
- Exact public API schemas belong to the public API client contract ticket. Target module ownership belongs to the module-seams ticket. Physical Notion translation belongs to the Notion adapter ticket. Concurrency and crash recovery belong to the idempotency/recovery ticket. Demo acceptance belongs to the demo-mode ticket. Migration sequencing belongs to the roadmap ticket.
- The inventory is complete only when every candidate behavior has a classification, stable fixture ID, evidence source, expected target disposition, and owning follow-up ticket when deferred.

## Testing Decisions

- Good parity tests assert behavior visible at a public workflow boundary: typed outcomes, durable semantic records, body sections, relations, artifacts, call counts, cleanup residue, and the absence of forbidden effects. They do not assert private helper calls or reproduce internal control flow.
- The main contract suite runs versioned scenarios through the public Capture, Application Analysis, and Resume Creation interfaces using deterministic recording implementations for workspace, model, matching, clock, identifier, and PDF dependencies.
- The ordered effect journal is part of the observable contract only where order carries a safety guarantee, including analysis body-before-properties, Resume artifacts-before-relations, Resume relation-last completion, and reverse compensation.
- Capture Evidence receives focused supporting tests because Chrome evidence collection and normalization occur before the backend workflow seam. Backend outcome fixtures begin with normalized Capture Evidence.
- Current Capture service tests provide prior art for `created`, `already_captured`, `needs_review`, parse-only, confirmation, invalid schema, and no-write outcomes.
- Current Application Analysis service and store tests provide prior art for bounded batches, failure isolation, stable analysis validation, body-first persistence, partial-write reporting, and repair without duplicate analysis.
- Current Resume Creation service tests provide prior art for eligibility checks, existing-Resume idempotency, pre-write evidence blocks, artifact success, and injected failure at Note, PDF, and final-attachment stages.
- Current Resume draft and fit-analysis tests provide prior art for claim-trace repair, role preservation, bullet-count gates, evidence classification, deterministic scoring, and insufficient-evidence blocks.
- Current Notion adapter tests provide prior art for schema validation, relation targets, inverse relation names, body structures, recursive reads, unlinked drafts, attachment, and archival cleanup.
- Each failure stage receives a fixture that proves both the returned outcome and the final residue. A cleanup test is incomplete if it checks only that a helper was called.
- Idempotency fixtures run the same logical action again from the post-success or partial-success state and prove the second run returns the reviewed existing or repaired outcome without duplicate model calls, records, Notes, relations, or PDFs.
- `parity_required` fixtures must pass against the frozen prototype harness and the target workflow implementation after normalization. `target_addition` fixtures are required only of the target. `superseded` fixtures document the replacement and may be used as negative tests to prevent legacy behavior from leaking into the target.
- `known_defect` scenarios document the observation but must not be added as passing target expectations.
- Adapter-specific contract tests may assert normalized Notion request intent and relation semantics, but raw Notion HTTP payload snapshots are not the primary parity gate.
- HTTP router tests remain responsible for reviewed auth, request validation, status mapping, and final response schemas. They do not define prototype parity for intentionally changed paths or transport.
- UI tests remain responsible for dashboard pending states, eligible-only queues, review-first capture, dirty-form protection, and result links. Those interaction details are not duplicated as backend workflow fixtures.
- Deterministic score fixtures pin the scoring-policy version, normalization-dictionary version, inputs, Evidence Strength results, Match Score or Fit Score, and generation-gate decision. Changing a threshold or weight requires an explicit fixture-version change and product decision.
- Privacy tests inspect normalized responses, persistent browser state, and logs to prove they exclude credentials, prompts, full Job Content, Master Resume content, raw model output, generated Resume body text, Notion payloads, and local PDF paths.
- Golden assertions use stable domain structures and text requirements. They avoid exact timestamps, generated IDs, Notion URLs, provider metadata, full model prose, PDF bytes, and cosmetic formatting unless a later contract explicitly makes one of those values stable.
- The final inventory must be reviewable without private Notion or resume data. Any captured regression input is redacted or replaced with representative deterministic content while preserving the behavior under test.
- Completion is verified by a coverage table showing every required area—Capture, Application Analysis, Resume Creation, Notion persistence, evidence validation, artifact creation, idempotency, failure cleanup, privacy, supersessions, target additions, known defects, and deferrals—with at least one owned fixture or an explicit rationale.

## Out of Scope

- Implementing the FastAPI server, React `/dashboard`, React Chrome extension, LangGraph workflows, adapters, or migration.
- Designing or locking the final production module interfaces and dependency directions.
- Locking exact HTTP paths, request and response schemas, generated TypeScript names, or auth/CORS implementation.
- Designing the exact physical-to-canonical Notion adapter mapping or changing any existing Notion database, property, relation, or record.
- Settling concurrency control, durable checkpoints, process-crash recovery, or automated resume of interrupted artifact commits.
- Prototyping dashboard or extension interaction details.
- Defining demo-mode reset, persistence, privacy, or presentation acceptance.
- Choosing dependency versions, runtime packaging, repository topology, deployment, or release ergonomics.
- Building the migration roadmap, implementation-ticket breakdown, or cutover sequence.
- Preserving legacy HTML, route names, NDJSON framing, Node/Python process boundaries, private helper structure, exact model wording, exact logs, or exact PDF bytes.
- Adding batch Resume Creation, missing-PDF repair, general Notes behavior, application editing, or record management outside Notion.

## Further Notes

- The working prototype remains the executable behavioral reference until parity-based cutover, but only behavior classified as `parity_required` becomes a migration requirement.
- The reviewed final-app route, dashboard, extension, Notion schema, and AI workflow documents are the authority for `superseded` and `target_addition` classifications.
- Older proposed documents that still describe separate React pages, streamed analysis, or `/api/job-postings/*` routes are known drift and must not override the reviewed contracts.
- The physical workspace currently uses legacy Job Posting names while the canonical domain uses Application. The inventory must keep those two layers explicit so future adapter work can preserve data without weakening the domain model.
- The focused prototype module suites currently pass. Local HTTP server tests may fail in restricted environments when binding `127.0.0.1`; that environment limitation is not a product parity outcome.
- Resolution assets must remain linked from this ticket, and later contract changes must update both the versioned corpus and the parent map pointer when their decision gist changes.

## Answer

The prototype parity contract is recorded in [Merida Prototype Parity Inventory](../assets/prototype-parity-inventory.md) and the versioned machine-readable corpus under `test/parity/fixtures`.

The inventory classifies 27 fixtures across `parity_required`, `superseded`, `target_addition`, `known_defect`, and `deferred`. Seventeen observations execute through the confirmed public workflow seams for Capture Evidence, Capture, Application Analysis, Resume Creation, Notion compatibility, and backend credential ownership. They cover Capture Evidence provenance and limits, the full Capture outcome/persistence matrix, eligible bounded analysis queue selection, sequential analysis failure isolation, evidence validation, body-first partial persistence, repair without another model call, Resume source and evidence guardrails, cross-role claim rejection, existing-Resume idempotency, successful canonical artifacts, relation compatibility, backend-only credentials, and state-backed compensation after Note, PDF, and final-attachment failures.

Migration parity preserves domain outcomes, evidence guardrails, semantic Notion effects, idempotency, artifact completion, and cleanup. It intentionally does not preserve backend-rendered pages, legacy route names, NDJSON, the `1..25` batch range, the Node/Python process split, hard-coded Resume roles, local PDF paths, exact model prose, or exact PDF bytes. Deterministic Match Score repair, canonical Resume Document rendering, unchanged non-work sections, typed cleanup state, and strict privacy behavior remain target additions.
