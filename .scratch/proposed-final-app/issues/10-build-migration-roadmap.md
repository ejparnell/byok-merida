# Build the dependency-ordered migration and cutover roadmap

Type: grilling
Labels: ready-for-agent
Status: resolved
Blocked by: 08, 09
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

What dependency-ordered vertical slices, parity fixtures, documentation updates, entry and exit criteria, fallback points, and per-workflow cutover gates should take Merida from the frozen prototype to the final app while keeping the prototype runnable until full end-to-end parity?

## Answer

## Problem Statement

Merida has settled the final app's product shape, module seams, public API, existing-Notion compatibility rules, runtime topology, concurrency and recovery boundaries, and removal of demo mode. A production-shaped FastAPI, React dashboard, React Chrome extension, generated API client, and credential-free acceptance gate already prove the target topology. The real Notion stores, task-specific DeepSeek adapters, complete Matching and evidence policies, artifact commit behavior, and operational cutover are not yet at prototype parity.

Without one dependency-ordered migration roadmap, implementation could port horizontal layers that cannot produce a usable workflow, retire prototype routes before their replacements are proven, test fakes more thoroughly than the real adapters, weaken evidence or cleanup guardrails, or let the proposed documentation describe an impossible mixture of prototype and final behavior. A single all-at-once cutover would also remove the executable reference and fallback before the highest-risk Resume Creation effects have been validated against the existing Notion workspace.

The operator needs a sequence that delivers and accepts one complete workflow at a time. Every slice must preserve the frozen prototype as an independently runnable reference until all real workflows pass parity, must distinguish automated credential-free acceptance from manual real-environment smoke evidence, and must leave a documented fallback point that does not require reversing or rewriting existing Notion data.

## Solution

Migrate through dependency-ordered vertical slices under one acceptance seam: the root final-app verification gate rooted at the FastAPI ASGI application and emitted OpenAPI contract. Workflow-specific store conformance suites, parity fixtures, recovery tests, generated-client checks, and React-consumer tests contribute to that gate rather than creating separate top-level acceptance systems.

The order is: freeze and reconcile migration authority; remove demo product behavior and stabilize the real-only shell; complete shared Notion, DeepSeek, Matching, journal, privacy, and fixture infrastructure; cut over real Application Capture; cut over real Application Analysis; cut over real Resume Creation; run full end-to-end real-runtime acceptance; switch the default operator commands and documentation; then archive the prototype only after an observation window.

Capture cuts over first because it establishes canonical Application identity and unchanged Notion writes without depending on another LLM workflow. Analysis follows because it consumes captured Applications and produces the durable analysis and Match Score required by Resume Creation. Resume Creation cuts over last because it depends on both earlier workflows and owns the widest evidence, Note, PDF, relation, compensation, and recovery surface.

"Cut over" means the final workflow becomes the documented operator path after its automated gate and a bounded real-environment smoke run pass. It does not mean deleting the prototype equivalent. During coexistence, fallback is operational: stop the final runtime, record and reconcile any ambiguous in-flight effect from the journal, and run the still-independent prototype. There is no automatic runtime fallback, dual write, shared mutable state between runtimes, or request routing from one implementation to the other.

## User Stories

1. As the Merida operator, I want the prototype to remain runnable throughout migration, so that I retain a proven fallback until the final app reaches end-to-end parity.
2. As the Merida operator, I want one workflow cut over at a time, so that a failure has a small and understandable blast radius.
3. As the Merida operator, I want Capture migrated before Analysis and Resume Creation, so that later workflows consume canonical Applications created through the accepted source boundary.
4. As the Merida operator, I want Analysis migrated before Resume Creation, so that Resume Creation consumes durable, final-app analysis rather than an unproven intermediate representation.
5. As the Merida operator, I want each cutover backed by automated and real-environment evidence, so that credential-free tests do not overstate production readiness.
6. As the Merida operator, I want explicit entry and exit criteria for every slice, so that progress is based on observable evidence rather than implementation completion claims.
7. As the Merida operator, I want a documented fallback point before every workflow cutover, so that I can recover without renaming or migrating Notion data.
8. As the Merida operator, I want ambiguous partial effects surfaced before fallback, so that switching runtimes does not hide a draft, relation, or artifact requiring repair.
9. As the Merida operator, I want the final app to use my existing Notion workspace unchanged, so that migration preserves records, views, formulas, relations, and history.
10. As the Merida operator, I want no dual writes during coexistence, so that the prototype and final app cannot create competing durable effects for one action.
11. As the Merida operator, I want only one runtime active for a mutating workflow during a smoke run or cutover, so that domain-key idempotency is not mistaken for cross-runtime coordination.
12. As the Merida operator, I want final Capture to preserve review-first `Fill Form` and `Create in Notion`, so that I confirm parsed content before it reaches Notion.
13. As the Merida operator, I want canonical Job URL duplicates to return the existing Application, so that repeated Capture remains safe across the migration.
14. As the Merida operator, I want Capture failures to leave no completed record, so that the Applications database remains trustworthy.
15. As the Merida operator, I want only eligible Applications shown in the Analysis Queue, so that every dashboard item can run without record-management controls.
16. As the Merida operator, I want bounded sequential Analysis to continue after one item fails, so that one malformed Application does not discard valid work.
17. As the Merida operator, I want Analysis repair to reuse an existing readable body, so that retries do not repeat model work or append duplicate content.
18. As the Merida operator, I want Match Score calculated and recovered deterministically, so that model variability cannot change the durable score during repair.
19. As the Merida operator, I want Resume Creation limited to one Application at a time, so that artifact effects and recovery remain understandable.
20. As the Merida operator, I want an existing Job-Specific Resume returned before generation, so that retries never create duplicate artifacts.
21. As the Merida operator, I want insufficient or unsupported evidence blocked before writes, so that migration never weakens resume truthfulness.
22. As the Merida operator, I want Notion Resume content and PDF content rendered from one validated Resume Document, so that application artifacts cannot drift.
23. As the Merida operator, I want Resume, Note, and PDF effects compensated in reverse order when completion fails, so that incomplete work does not appear complete.
24. As the Merida operator, I want the final Resume Attachment written last, so that the existing relation remains the durable completion marker.
25. As the Merida operator, I want manual recovery instructions for ambiguous residue, so that the system never guesses when provider state cannot be proven.
26. As the Merida operator, I want the dashboard to remain an LLM process console, so that editing and record repair stay in Notion during and after migration.
27. As the Merida operator, I want model names visible but not editable in the dashboard, so that backend configuration remains the authority.
28. As the Merida operator, I want no demo mode, reset operation, fixture workspace, or fictional fallback, so that readiness always describes the real runtime.
29. As a maintainer, I want one root final-app verification gate, so that every migration slice satisfies the same repository-wide acceptance contract.
30. As a maintainer, I want the FastAPI ASGI application and OpenAPI document to remain the highest test seam, so that backend behavior and both React consumers share one public contract.
31. As a maintainer, I want every `parity_required` fixture assigned to an owning slice, so that no protected prototype outcome is lost between tickets.
32. As a maintainer, I want every `target_addition` fixture mandatory before its workflow cuts over, so that accepted final-app improvements are not postponed behind nominal parity.
33. As a maintainer, I want superseded prototype behavior represented by negative target checks where valuable, so that old pages, transports, paths, modes, and private logging do not return.
34. As a maintainer, I want real Notion stores and deterministic fakes to share behavioral conformance suites, so that test infrastructure proves the same workflow-owned interfaces.
35. As a maintainer, I want task-specific DeepSeek adapters verified against recorded responses and deterministic contract examples, so that provider formatting differences cannot bypass evidence validation.
36. As a maintainer, I want automated acceptance to require no credentials or network calls, so that the complete gate remains deterministic and safe for CI.
37. As a maintainer, I want real-environment smoke runs kept bounded and non-destructive, so that production integration evidence does not become an uncontrolled test suite.
38. As a maintainer, I want one-process production-shaped serving tested before cutover, so that development-only process topology does not hide deployment failures.
39. As a maintainer, I want generated OpenAPI and client artifacts checked for freshness, so that dashboard and extension calls cannot drift from FastAPI.
40. As a maintainer, I want privacy checks in every slice, so that prompts, credentials, private content, raw model output, provider payloads, and local paths stay out of normal logs and responses.
41. As a maintainer, I want fault injection at each durable effect boundary, so that cleanup and residue claims are proven rather than inferred.
42. As a maintainer, I want restart reconciliation tests for the effect journal, so that a process interruption cannot silently strand an operation.
43. As a maintainer, I want fixed slice dependencies and small implementation tickets, so that agents cannot start Resume or retirement work before prerequisite contracts are green.
44. As a maintainer, I want each slice to end with documentation reconciliation, so that operator instructions never lag behind the active runtime.
45. As a maintainer, I want prototype commands to retain their original meaning during coexistence, so that fallback does not depend on remembering renamed commands.
46. As a maintainer, I want final-app commands namespaced until default cutover, so that running the intended runtime is explicit.
47. As a maintainer, I want cutover evidence recorded with the code revision, fixture version, configuration readiness, and observed outcomes, so that acceptance is auditable.
48. As a maintainer, I want a prototype observation window after default cutover, so that operational defects can be found before reference code is archived.
49. As a maintainer, I want parity fixtures retained after prototype retirement, so that future changes continue to protect migration-earned behavior.
50. As a maintainer, I want historical prototype documentation preserved and clearly labeled, so that it remains useful evidence without being mistaken for current operations.
51. As a maintainer, I want the final docs to identify one authoritative setup, operation, recovery, schema, workflow, and API contract, so that contributors do not synthesize behavior from conflicting drafts.
52. As an implementation agent, I want each ticket to name its prerequisites, fixture subset, external behavior, fallback, and verification commands, so that I can complete it without reconstructing the roadmap.

## Implementation Decisions

### Roadmap authority and slice rules

- This specification is the ordering authority for implementation tickets. The reviewed domain, module, API, Notion, runtime, concurrency, recovery, and real-only decisions remain the behavior authorities within their areas.
- Implementation is split by end-to-end workflow capability, not by horizontal framework layer. A slice includes its workflow module, real adapters, public route behavior, generated client impact, React caller behavior, tests, operational evidence, and documentation.
- The root final-app verification gate is the single automated acceptance seam. Lower-level suites are owned by their modules but must be reachable from that gate.
- A slice cannot cut over merely because code exists or fake-backed tests pass. It must satisfy its automated exit criteria and its bounded real-environment smoke gate.
- The prototype remains frozen except for a critical safety fix or the smallest instrumentation needed to preserve the parity oracle. Any such change requires updating and versioning the parity corpus before target acceptance.
- New target behavior is classified as `parity_required`, `target_addition`, or `superseded`. Unclassified behavior cannot silently become a cutover requirement.
- Each implementation ticket must be independently reviewable and must leave both prototype and final-app verification green. Tickets should be tracer bullets within one slice: contract and fixtures, pure policy, real adapter, public/UI integration, recovery, then cutover evidence.

### Slice 0: Reconcile the real-only acceptance shell

- Entry: the public `/api/v1` contract, generated client, React dashboard, React extension, final-app commands, test-only dependency injection, and frozen prototype commands exist.
- Remove all demo product composition, settings, schemas, reset operations, fixture persistence, generated-client exports, UI labels, and reset concurrency concepts. Test fakes remain available only through explicit application-factory injection.
- Reconcile the final-app documentation so it no longer promises demo mode, a selectable adapter, or a credential-free product workspace.
- Establish a migration evidence record format containing slice name, code revision, parity fixture schema version, automated gate result, real configuration checks, smoke actions, durable IDs created or reused, recovery status, and the approved fallback point. It must contain no credentials or private content.
- Exit: the full final-app gate passes without credentials or network calls; static checks find no shipped demo administration surface; ordinary startup composes only real adapters and blocks truthfully when configuration or workflow adapters are incomplete; the prototype still starts and tests independently.
- Fallback: no operator workflow has moved. Revert only final-app shell changes if necessary; the prototype remains the sole operational runtime.

### Slice 1: Complete shared migration infrastructure

- Entry: Slice 0 is green and all decisions from the Notion, runtime, concurrency, recovery, and no-demo specifications are reflected in tests or explicit implementation tickets.
- Build the shared physical-name translation primitives used by the three narrow Notion stores without exposing a broad workspace interface. Complete safe property decoding, body-section parsing and writing, pagination translation, typed provider failures, relation-target validation, and workflow-scoped schema capability checks.
- Establish task-specific DeepSeek transport infrastructure, JSON encoding, schema validation, safe observability, timeouts, and recorded-response testing without creating a generic model platform or letting provider types enter workflow interfaces.
- Port shared deterministic Matching and versioned normalization policies required by Analysis and Resume Creation. Pure policies land before the workflows that consume them.
- Complete the content-free effect journal, fixed lock ordering, fail-fast workflow and per-Application exclusion, reverse compensation primitives, restart reconciliation, and typed manual-recovery residue.
- Turn the parity inventory into slice-addressable test manifests. Preserve fixture identifiers and schema version; do not duplicate fixtures into unrelated suites.
- Exit: the three store conformance harnesses can run against deterministic fakes and deterministic Notion transport recordings; privacy and journal tests pass; shared policies have versioned fixtures; no real workflow is represented as ready merely because infrastructure exists.
- Fallback: shared infrastructure is dormant behind blocked real composition. The prototype remains the operator path for all workflows.

### Slice 2: Cut over Application Capture

- Entry: Slices 0 and 1 are green; the Capture store interface and public prepare/confirm outcomes are locked; the extension's review-first interaction is accepted; a dedicated safe real Capture target is identified.
- Implement the real `CaptureStore` against the unchanged Applications database. Preserve canonical Job URL identity, exact Captured URL evidence when supported, stable Capture Summary and Job Content, workflow-scoped schema validation, `To Apply` defaults, and typed warnings and failures.
- Keep parsing and review free of workspace writes. Confirmation revalidates the reviewed fields, rechecks the canonical duplicate, journals the create effect, and returns the existing Application for a duplicate.
- Required fixtures are CAPTURE-EVIDENCE-001, CAPTURE-001, CAPTURE-002, CAPTURE-003, NOTION-001, PRIVACY-001, and PRIVACY-ADD-001. Relevant superseded Capture behavior becomes negative tests, including required Location, Quick Capture, and obsolete routes.
- Automated exit: fake and Notion-recording conformance pass; public ASGI and generated-client tests cover prepared, needs-review, created, already-captured, blocked, and failed outcomes; extension tests cover dirty review, preserved edits, auth, and no private persistence; failure injection proves no completed record after partial failure.
- Real cutover gate: readiness validates only Capture capabilities; prepare performs no Notion write; one reviewed Application is created with correct defaults and readable sections; repeating the canonical URL returns the same Application; a controlled invalid input creates nothing; logs and responses pass privacy inspection.
- Cutover: document the React side panel as the Capture operator path. Do not expose or route Capture through the prototype from the final app.
- Fallback: quiesce Capture, reconcile any journal entry, confirm whether a Notion page was created, and resume with the prototype extension. The created Application remains valid shared workspace data and is not rolled back solely because the operator changes runtimes.

### Slice 3: Cut over Application Analysis

- Entry: real Capture is accepted; shared Matching and Analysis model infrastructure is green; `ApplicationAnalysisStore` passes conformance; a bounded set of safe eligible Applications exists.
- Implement the real Analysis store and task-specific DeepSeek Analysis adapter. Read only stable Job Content, validate three-sentence summaries and evidence-backed Skill Signals, calculate Match Score deterministically, write the analysis body before final properties, and repair existing canonical or legacy analysis without another model call.
- Preserve eligible-only queue semantics, opaque cursors, deterministic ordering, batch limits from one through ten, sequential execution, fail-fast overlap rejection, and per-item failure isolation in one final typed result.
- Required fixtures are ANALYSIS-001, ANALYSIS-002, ANALYSIS-003, ANALYSIS-004, ANALYSIS-ADD-001, NOTION-001, PRIVACY-001, and PRIVACY-ADD-001. Negative target tests cover queue leakage, limits above ten, NDJSON streaming, provider-supplied final Match Score, and duplicate body writes.
- Automated exit: recorded DeepSeek responses and deterministic fakes satisfy the same output contract; unsupported evidence and generic traits are rejected; body-first failure and exact repair are proven; overlap and restart tests release locks and reconcile journal state; dashboard tests show pending state followed by one final result and reset the queue cursor after success.
- Real cutover gate: readiness validates Analysis store and model capability; a bounded run analyzes one safe Application; an injected or prepared invalid item does not stop a later valid item; stored body and Match Score agree; a repair scenario performs no second model request; normal logs contain no source or model payloads.
- Cutover: document the dashboard as the Analysis operator path. Existing analysis produced by either runtime remains readable through legacy-compatible body parsing.
- Fallback: stop new Analysis runs, wait for or reconcile the single active run, inspect body-first/property-final residue, and resume the prototype Analysis workflow only after no ambiguous active effect remains. Never run both Analysis implementations concurrently.

### Slice 4: Cut over Resume Creation

- Entry: real Capture and Analysis are accepted; the selected Application has readable Job Content and canonical or legacy analysis; exactly one readable Master Resume is available; shared Matching, Resume model contracts, PDF storage, and journal primitives are green.
- Port Fit Requirement extraction, deterministic matching, evidence classifications, role-owned claim validation, one bounded repair attempt, canonical Resume Document construction, Resume Fit Analysis rendering, Notion Resume rendering, PDF rendering, and `ResumeArtifactCommitter` behind `ResumeCreationStore`.
- Preserve all Master Resume roles and chronology, five to seven evidence-backed bullets per role with six preferred, unchanged non-work sections, direct-or-adjacent evidence gates, human-readable claim traces, one Job-Specific Resume per Application, and `already_created` before new effects.
- Render Notion and PDF outputs from the same validated Resume Document. Stage Resume, Note, and PDF before attaching the final Resume relation. Journal each external effect, compensate in reverse order, and return explicit incomplete cleanup state when residue cannot be proven absent.
- Required fixtures are RESUME-001, RESUME-002, RESUME-003, RESUME-004, ARTIFACT-001, CLEANUP-001, CLEANUP-002, TARGET-ADD-002, NOTION-001, PRIVACY-001, and PRIVACY-ADD-001. Negative target tests cover hard-coded personal templates, local path responses, `already_exists`, a zero-to-one public score, cross-role claims, and incidental PDF byte snapshots.
- Automated exit: all precondition and evidence failures occur before artifacts; the existing-Resume path performs no model or artifact work; Notion and PDF semantic content agree; final relation is last; failure injection at Resume, Note, PDF, and attachment boundaries proves reverse compensation and truthful residue; restart reconciliation and per-Application exclusion pass.
- Real cutover gate: create one Job-Specific Resume for a safe Application and inspect its evidence, chronology, Note relations, PDF download, and final attachment; repeat returns `already_created`; run one controlled pre-effect block; exercise compensation with a safe fault-injection boundary when available or a deterministic provider recording when a real destructive fault would be unsafe.
- Cutover: document the dashboard as the Resume Creation operator path and keep one-at-a-time operation. Artifact management and record editing remain in Notion and the backend-owned download surface.
- Fallback: disable new Resume Creation, reconcile the journal and all possible Resume, Note, PDF, and relation residue, and use the prototype only after the Application has no ambiguous completion marker. Completed final-app artifacts remain authoritative and must cause the prototype to return its existing-result behavior.

### Slice 5: Full real-runtime acceptance and default cutover

- Entry: all three workflow cutover gates are accepted independently and their evidence records identify no unresolved residue.
- Run a clean-install final-app verification, generated-contract freshness check, production builds, one-process production-shaped serving check, and the entire parity corpus. The prototype parity suite must also remain green at this point.
- Run one bounded end-to-end real path from extension review through Capture, dashboard Analysis, Resume Creation, Note and PDF inspection, duplicate retries, and readiness recheck. Use a deliberately selected Application and record only safe identifiers and outcomes.
- Prove restart behavior with no active mutation, with a recoverable journal entry, and with an ambiguous entry that blocks and requests manual recovery. Prove fail-fast overlap behavior without relying on multiple workers.
- Reconcile all proposed documentation into one coherent current final-app set. Update setup, commands, configuration, API/client generation, extension loading, workflows, schema compatibility, privacy, recovery, smoke checks, cutover, and fallback guidance. Mark prototype docs historical but keep them intact.
- Change the default operator commands only in this slice. The final app becomes the default start and verification path; explicit prototype commands are added or retained so the reference stays runnable during the observation window.
- Exit: the final gate, prototype gate, full parity corpus, real end-to-end smoke path, recovery checks, production-shaped serving, and documentation audit pass from a clean checkout; all workflow readiness is true with real configuration; no demo or legacy target surface is shipped.
- Fallback: restore the previous command/documentation pointers, reconcile active journal state, and use the explicit prototype runtime. Do not revert valid Notion records or artifacts and do not switch automatically based on runtime errors.

### Slice 6: Observation and prototype retirement

- Entry: the final app is the default runtime and has completed an agreed observation window with representative Capture, Analysis, Resume, retry, restart, and recovery outcomes.
- During the observation window, fixes land in the final app while the prototype remains frozen and runnable. Any discovered parity gap adds or corrects a versioned fixture before the target fix is accepted.
- Retirement requires no unresolved high-severity parity or recovery defects, no need to use the prototype fallback during the observation window, current operational docs, and an archived cutover evidence record.
- Archive or remove obsolete Node routes, HTML pages, sidecar startup, and legacy extension implementation only after retirement approval. Preserve historical documentation, the parity inventory, machine-readable fixtures, relevant ADRs, and migration evidence.
- After retirement, prototype commands may become archival verification commands or be removed if their dependency burden is unsafe, but this requires a separate cleanup ticket and must not weaken the final-app gate.
- Exit: the repository has one supported runtime, one current operator documentation set, one public API/client contract, retained parity evidence, and no ambiguous references that direct operators to the prototype.
- Fallback after retirement is restore-from-version-control, not a supported runtime switch. The retirement evidence must identify the last revision where the frozen prototype was runnable.

### Documentation authority and implementation-ticket breakdown

- Documentation is reconciled at the end of every slice, not deferred entirely to default cutover. Before default cutover, current prototype operations and proposed final-app operations remain explicitly separated.
- The reviewed route, frontend, extension, Notion schema, AI workflow, architecture, codebase structure, workflow, and migration documents must agree on canonical domain language, workflow eligibility, real-only composition, public outcomes, recovery, and operator surfaces.
- The migration plan becomes a concise operator-facing summary of this roadmap. The issue specification remains the implementation-order authority and should not be copied wholesale into user documentation.
- Create implementation tickets in dependency order within each slice. Every ticket states its blocking edges, owned interfaces, fixture IDs, external acceptance behavior, documentation impact, and fallback. No ticket may combine real changes from more than one workflow merely to reduce ticket count.
- CI configuration, supported-platform installation ergonomics, and prototype deletion are separate tickets within Slices 5 and 6; they must not block earlier workflow implementation unless they are required by the single verification gate.

## Testing Decisions

- A good migration test asserts external behavior: typed HTTP outcomes, emitted OpenAPI, generated-client operations, visible dashboard or extension state, canonical domain values, semantic Notion effects, artifact metadata and content, exclusion behavior, compensation results, restart reconciliation, and safe logs. It does not assert private helper calls, concrete class names, incidental provider payload shapes, exact model prose, PDF bytes, or source layout.
- The single highest seam is the root final-app verification gate. Its contract authority is the FastAPI ASGI application and emitted OpenAPI document with deterministic test dependencies explicitly injected behind the same workflow interfaces used by real composition.
- Public-contract tests exercise both success and typed non-success variants, including blocked readiness, review required, already captured, per-item Analysis failure, already created, invalid cursor, workflow conflict, cleanup incomplete, and artifact download failure.
- Generated-client freshness and both React production builds are acceptance requirements in every slice that changes public behavior. The dashboard and extension call the generated client only through their thin consumer-owned adapters.
- Store conformance suites are interface-specific. `CaptureStore`, `ApplicationAnalysisStore`, and `ResumeCreationStore` each run the same semantic cases against deterministic fakes and deterministic Notion transport recordings; provider-specific mapping tests cover physical names, pagination, relations, body blocks, and safe error normalization.
- Model adapter tests are task-specific. Recorded DeepSeek responses and deterministic model fakes must satisfy the same schema, evidence, repair, timeout, and error-normalization requirements, while tests remain offline and secret-free.
- Parity fixture ownership is fixed by slice. Capture owns CAPTURE-EVIDENCE-001 and CAPTURE-001 through CAPTURE-003. Analysis owns ANALYSIS-001 through ANALYSIS-004 and ANALYSIS-ADD-001. Resume Creation owns RESUME-001 through RESUME-004, ARTIFACT-001, CLEANUP-001, CLEANUP-002, and TARGET-ADD-002. NOTION-001 and the privacy fixtures run in every applicable workflow slice.
- `parity_required` fixtures must remain green against the frozen prototype and normalized target outcomes until prototype retirement. `target_addition` fixtures are required only against the target before cutover. `superseded` fixtures inform negative target assertions and do not force the target to reproduce obsolete implementation details.
- Concurrency tests prove one-worker fail-fast workflow exclusion, per-Application exclusion across workflow types, fixed lock ordering, cancellation release, no automatic POST retry, and safe duplicate re-entry through domain-key idempotency.
- Recovery tests inject failure after every durable effect. They assert journal state, reverse compensation order, durable completion markers, typed clean versus incomplete cleanup, restart reconciliation, and blocking manual recovery when provider state is ambiguous.
- Privacy tests inspect normal logs, public responses, generated bundles, and journal records for credentials, auth headers, prompts, full Job Content, Master Resume content, raw model output, Notion payloads, generated Resume text, and local artifact paths.
- UI tests assert accepted interaction outcomes rather than DOM structure: review-first Capture and dirty-form protection; eligible-only queues; pending then final Analysis results; retained Resume artifact links; typed conflicts and blocked states; no record editing, model selection, Quick Capture, streaming transport, demo controls, or reset behavior.
- Real-environment smoke tests are manual cutover evidence, not part of credential-free CI. They are bounded to explicitly selected records, avoid intentional destructive failures when provider recordings can prove the same boundary safely, and require inspection of durable Notion and artifact effects.
- A workflow cannot be declared ready when its fake path passes but its real store or model adapter remains blocked. Readiness must be workflow-scoped and must truthfully name missing configuration or capabilities without exposing secrets.
- Prior art includes the existing prototype parity corpus, ASGI public-contract tests, generated-client adapter tests, dashboard-session tests, extension Capture-session tests, workflow-owned store conformance helpers, deterministic Notion transport recordings, effect-order tests, fault-injection cleanup tests, and restart recovery tests.
- Completion of the roadmap requires the final-app gate and frozen prototype gate to pass together immediately before default cutover. Prototype retirement later removes the requirement to execute the prototype gate but retains its fixture corpus in final-app regression coverage.

## Out of Scope

- Implementing the migration, adapters, workflow ports, CI, command cutover, or prototype retirement in this specification ticket.
- Renaming or migrating existing Notion databases, properties, relations, records, or user-authored content.
- Dual writes, live traffic splitting, automatic fallback, cross-runtime locks, data replication, or a shared runtime composition between prototype and final app.
- A demo, sample, fixture, preview, sandbox, portfolio, offline, or resettable product mode.
- Cloud hosting, remote authentication, multi-user tenancy, multiple FastAPI workers, background job infrastructure, distributed coordination, or automated crash resumption.
- Application, Resume, Note, schema, configuration, or recovery editing in the dashboard or extension; Notion and documented manual operations remain the management surfaces.
- Quick Capture, separate Analysis or Resume pages, streamed Analysis transport, batch Resume Creation, missing-PDF repair, automated application submission, or a general-purpose Notes workflow.
- Supporting multiple LLM providers, operator model selection, a generic agent platform, or arbitrary prompt configuration.
- Preserving prototype route names, HTML, local file paths, hard-coded templates, score scales, internal module boundaries, or other behavior classified as superseded.
- Deleting historical documentation, ADRs, parity fixtures, or cutover evidence as part of runtime retirement.

## Further Notes

- The highest practical acceptance seam is intentionally one level above any workflow module: the FastAPI ASGI/OpenAPI contract reached by the root final-app gate. Workflow interface tests remain essential beneath it, but they do not become competing definitions of release readiness.
- The roadmap separates automated acceptance from real-environment evidence because both are necessary: deterministic fakes provide exhaustive, credential-free fault coverage, while bounded smoke runs prove that current Notion and DeepSeek integrations satisfy those interfaces.
- Coexistence is temporal and operational, not architectural. The two runtimes share the user's Notion workspace only through compatible domain effects; they do not import each other, delegate to each other, or coordinate active mutations.
- Capture, Analysis, and Resume Creation may be cut over independently for operator use, but the prototype is not retired workflow by workflow. It remains intact as the executable behavioral reference until full real-runtime acceptance and the observation window complete.
- A completed durable effect is not undone merely to exercise fallback. Fallback means returning future operations to the frozen prototype after reconciliation, not attempting to restore the workspace to a pre-migration snapshot.
- The observation window length is an operational choice to make when implementation reaches Slice 6. Its acceptance signals are specified here; calendar duration is deliberately not invented in advance.
