# Set the concurrency, idempotency, and recovery boundaries

Type: grilling
Labels: ready-for-agent
Status: resolved
Blocked by: 05, 06, 07
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

What v1 execution rules should govern overlapping analysis and resume requests, per-Application exclusion, request retries, idempotency keys or durable markers, partial Notion and PDF commits, compensation, process crashes, and the boundary between automated and manual recovery without a durable LangGraph checkpointer?

## Problem Statement

Merida's public API, workflow modules, Notion compatibility adapter, and local
runtime topology now agree on the normal Capture, Application Analysis, and
Resume Creation paths. They do not yet define what happens when two mutations
overlap, a browser repeats a request after losing its response, Notion accepts
only part of a multi-effect commit, PDF publication fails, the FastAPI process
stops between effects, or automatic cleanup itself fails.

Without one recovery contract, otherwise-correct implementations could run two
analysis batches over the same Applications, create duplicate Applications or
Job-Specific Resumes, steal stale locks, retry unsafe Notion writes, mistake an
orphaned draft for a completed artifact, delete operator-authored content, or
report success while cleanup residue remains. A durable LangGraph checkpointer
would not solve these effect-level problems and would unnecessarily persist
private workflow state.

## Solution

Run v1 as one loopback-bound FastAPI process with one worker. Add a small
backend-owned execution coordinator that provides fail-fast workflow gates,
canonical-Job-URL exclusion for Capture, and per-Application exclusion shared
by Application Analysis and Resume Creation. Locks are process-local safety
mechanisms, not durable completion evidence; they are always released with the
request task and are never stolen by elapsed-time heuristics.

Keep the public idempotency surface unchanged. Capture rechecks canonical Job
URL under its exclusion key, Application Analysis repairs a complete persisted
analysis body whose final properties are incomplete, and Resume Creation checks
the final Application-to-Resume relation before any new effects. The generated
client sends no idempotency header and never automatically retries a POST.

Use Notion's stable Application Analysis section and final Resume relation as
the primary durable completion markers. Add a minimal, versioned, content-free
effect journal for Capture and Resume Creation because their partially created
page, Note, and PDF effects cannot always be reconstructed safely from domain
relations alone. The journal stores correlation and artifact identifiers,
phases, timestamps, and cleanup results, but never Job Content, resume evidence,
prompts, model output, credentials, or generated document bodies.

Resume Creation continues to commit an unlinked Resume, atomically publish its
PDF, create its Resume Fit Analysis Note, and attach the final relation last.
Known failures compensate in reverse order. After a process restart, bounded
reconciliation treats a present final relation as completed and otherwise
cleans only artifacts proven to belong to the unfinished journal entry.
Ambiguous or incomplete cleanup becomes manual recovery through a local
maintenance command; normal workflow routes never expose arbitrary cleanup or
record-management operations.

The highest acceptance seam is the configured FastAPI ASGI application using
controlled fake Notion, model, PDF, clock, and failure adapters. Tests overlap
real requests, interrupt execution after each durable effect, restart the app,
and assert the same public outcomes and durable residue that a local operator
would observe.

## User Stories

1. As the local operator, I want only one Application Analysis batch to run at a time, so that the same eligible queue is not processed twice concurrently.
2. As the local operator, I want only one Resume Creation mutation to run at a time, so that v1 preserves its one-at-a-time workflow promise.
3. As the local operator, I want Application Analysis and Resume Creation excluded from mutating the same Application simultaneously, so that eligibility and final markers cannot race.
4. As the local operator, I want different Capture confirmations to proceed independently, so that one slow job board does not block unrelated captures.
5. As the local operator, I want concurrent confirmation of the same canonical Job URL to produce one Application, so that duplicate clicks do not create duplicate pursuits.
6. As the local operator, I want a repeated successful Capture confirmation to return `already_captured`, so that a lost browser response is recoverable.
7. As the local operator, I want a repeated successful Resume Creation request to return `already_created`, so that a lost final response does not duplicate artifacts.
8. As the local operator, I want an overlapping mutation rejected promptly, so that the dashboard does not wait behind an invisible server queue.
9. As the local operator, I want an overlap response to use the existing typed technical boundary, so that the UI can explain that work is already in progress.
10. As the local operator, I want queue reads and readiness checks to remain available during mutations, so that I can inspect the app without interrupting work.
11. As the local operator, I want stale queue cursors rejected after mutations, so that a concurrent read cannot present an invalid snapshot as current.
12. As the local operator, I want a demo reset rejected while any mutation is active, so that reset cannot erase state beneath a running workflow.
13. As the local operator, I want active demo reset to exclude every new mutation, so that the restored fixture is internally consistent.
14. As the local operator, I want a browser disconnect not to trigger an automatic duplicate POST, so that uncertainty is resolved by durable state rather than replay.
15. As the local operator, I want provider timeouts bounded, so that a hung provider does not hold a workflow gate forever.
16. As the local operator, I want timed-out work to release its process-local locks, so that a failed request does not poison the running process.
17. As the local operator, I want server restart to clear only process-local locks, so that a previous process cannot leave a false in-progress state.
18. As the local operator, I want unfinished durable effects reconciled after restart, so that clearing locks does not hide partial work.
19. As the local operator, I want recovery to preserve operator-authored Notion content, so that automation never archives an ambiguous page merely because it looks incomplete.
20. As the local operator, I want failed automatic cleanup reported with a correlation identifier, so that I can inspect the exact recovery entry safely.
21. As the local operator, I want manual recovery scoped to a local maintenance command, so that the dashboard and extension stay focused on ordinary workflows.
22. As the local operator, I want manual recovery instructions to name safe record identifiers and actions without exposing private content, so that remediation is practical and privacy-preserving.
23. As the local operator, I want an unresolved recovery entry to block only its affected domain key, so that unrelated Applications can still be processed.
24. As the local operator, I want a corrupt recovery journal to block side-effecting mutations instead of being overwritten, so that evidence needed for cleanup is not destroyed.
25. As the local operator, I want completed journal entries compacted safely, so that local recovery metadata remains bounded.
26. As an extension user, I want Capture preparation to remain non-mutating and concurrent, so that opening or editing a review form cannot take a write lock.
27. As an extension user, I want Capture confirmation to canonicalize the URL before exclusion, so that tracking parameters and URL variants cannot evade duplicate protection.
28. As an extension user, I want the duplicate lookup repeated inside the exclusion boundary, so that a pre-lock check cannot race with another confirmation.
29. As an extension user, I want a known partial Capture page archived before a safe retry, so that an interrupted capture does not remain active beside the replacement.
30. As an extension user, I want an ambiguous active page treated as a conflict rather than archived automatically, so that existing workspace data is not guessed away.
31. As a dashboard user, I want the second Analysis run click rejected while a batch is running, so that I do not start another batch accidentally.
32. As a dashboard user, I want each Analysis item isolated from failures in other items, so that one failed Application does not abort the batch.
33. As a dashboard user, I want an item that becomes ineligible before its mutation to be skipped safely, so that stale queue membership does not force work.
34. As a dashboard user, I want a complete persisted Application Analysis body repaired without another model call, so that a crash before final properties is cheap to recover.
35. As a dashboard user, I want an incomplete trailing analysis section ignored when an earlier complete section exists, so that recovery uses stable persisted evidence.
36. As a dashboard user, I want an analysis state with no complete readable section blocked from automatic property repair, so that Merida does not invent a completion marker.
37. As a dashboard user, I want a restarted Analysis batch to select the current eligible queue, so that it does not resume a stale in-memory batch plan.
38. As a dashboard user, I want Resume Creation to revalidate eligibility inside its exclusion boundary, so that analysis or Notion edits cannot race the commit.
39. As a dashboard user, I want existing active Job-Specific Resume multiplicity treated as a workspace conflict, so that Merida never chooses an arbitrary completion artifact.
40. As a dashboard user, I want a Job-Specific Resume to remain unlinked until its Note and PDF exist, so that the final relation remains a trustworthy completion marker.
41. As a dashboard user, I want PDF publication to be atomic, so that a download never serves a partially written file.
42. As a dashboard user, I want a failed Resume commit compensated in reverse order, so that dependent artifacts are removed safely.
43. As a dashboard user, I want cleanup success reported as `completed`, so that I know a failed workflow left no known active residue.
44. As a dashboard user, I want cleanup failure reported as `incomplete`, so that a failed workflow is not mistaken for clean rollback.
45. As a dashboard user, I want a crash after final attachment recognized as completed, so that restart reconciliation never archives a valid Resume.
46. As a dashboard user, I want a crash before final attachment to clean only journal-owned artifacts, so that retry can start from a known state.
47. As a dashboard user, I want an existing completed Resume returned even when its historical Note or PDF is missing, so that this work does not silently become an artifact-repair feature.
48. As a backend developer, I want one execution coordinator injected at the composition root, so that workflow modules share exclusion rules without importing FastAPI globals.
49. As a backend developer, I want one effect-journal interface with real and in-memory test implementations, so that crash recovery is testable without coupling workflows to JSON storage.
50. As a backend developer, I want journal writes to use validation and atomic replacement, so that a process interruption cannot truncate the recovery record.
51. As a backend developer, I want journal entries written before the first external effect and advanced after each confirmed effect, so that recovery has the best available ownership evidence.
52. As a backend developer, I want non-idempotent provider writes excluded from generic transport retries, so that an ambiguous timeout cannot multiply effects.
53. As a backend developer, I want safe reads and idempotent target-state updates to use bounded retries, so that transient provider failures do not require unnecessary operator action.
54. As a backend developer, I want DeepSeek transport and structured-output retries to finish before persistence starts, so that model repair cannot repeat committed effects.
55. As a backend developer, I want every mutation assigned an internal run identifier, so that logs, journal entries, and safe public errors can be correlated.
56. As a backend developer, I want lock metadata excluded from public responses and normal browser state, so that internal execution details do not become API contracts.
57. As a backend developer, I want cancellation and exceptions to release locks in `finally` behavior, so that all terminal paths obey the same exclusion rule.
58. As a backend developer, I want no elapsed-time lock stealing, so that a merely slow provider call cannot be overlapped by a second mutation.
59. As a backend developer, I want multi-worker startup rejected, so that process-local exclusion is not presented as cross-process safety.
60. As a test author, I want deterministic barriers around durable effects, so that overlap and crash windows can be reproduced reliably.
61. As a test author, I want the app reconstructed against the same fake durable workspace and journal, so that restart recovery is tested rather than mocked away.
62. As a test author, I want effect traces and final durable state asserted instead of private lock calls, so that tests survive coordinator refactors.
63. As a test author, I want every crash point between Resume effects covered, so that relation-last completion and reverse cleanup are proven.
64. As a test author, I want every safe and unsafe retry class covered, so that provider retry policy cannot drift silently.
65. As a maintainer, I want the recovery contract to avoid a generic transaction engine, so that v1 remains understandable and feature-owned.
66. As a maintainer, I want durable graph checkpointing left out of v1, so that private graph state is not persisted without a retention and security decision.
67. As a maintainer, I want the frozen prototype to remain the real-workflow reference until these recovery tests pass, so that migration does not weaken proven safeguards.

## Implementation Decisions

### Runtime and exclusion model

- V1 supports exactly one loopback-bound FastAPI process with one ASGI worker. The startup path rejects a configured multi-worker or distributed execution mode. Cross-process locks, a task queue, and distributed leases require a new architecture decision.
- Introduce one backend-owned `ExecutionCoordinator` interface. The composition root injects one process-local implementation into Application Capture, Application Analysis, Resume Creation, and demo administration. Workflow modules do not read module-global lock maps.
- The coordinator exposes three concepts only: exclusive workflow gates, keyed domain exclusion, and immutable active-run metadata for safe diagnostics. It is not a scheduler, queue, background-job system, or transaction manager.
- Workflow gates are fail-fast. A second Application Analysis run, Resume Creation run, or demo reset returns the existing `409 conflict` technical envelope with a safe message and correlation identifier. Requests are not held in an invisible FIFO.
- Application Analysis has one global batch gate. Resume Creation has one global gate because v1 is explicitly one-at-a-time. Demo reset has one exclusive mutation gate that conflicts with every Capture confirm, Analysis run, and Resume Creation mutation.
- Capture preparation takes no mutation gate. Capture confirmation takes keyed exclusion on the canonical Job URL and repeats readiness and duplicate checks after acquiring it. Different canonical URLs may confirm concurrently.
- Application Analysis and Resume Creation use the same keyed exclusion namespace for canonical Application IDs. Analysis holds the key only while processing that Application, not for the entire batch. Resume Creation holds it from eligibility revalidation through final result or cleanup.
- Gate acquisition order is fixed: demo-reset exclusion, workflow gate, then domain key. A workflow never tries to acquire a broader gate while holding a narrower one. This prevents deadlock and makes overlap behavior deterministic.
- Queue and health reads do not take mutation locks. Their results are snapshots and may become stale immediately; existing cursor invalidation and post-mutation first-page reset rules remain authoritative.
- PDF downloads may overlap mutations because files become visible only through atomic publication. A missing or not-yet-published file retains the locked `pdf_not_found` behavior.
- Every mutation receives a new internal UUID run identifier and start time. Batch Analysis also assigns a distinct child run identifier per Application. These values may appear in safe logs and the effect journal but do not become client-supplied IDs or new public response fields.
- Locks are released on success, failure, cancellation, and unexpected exceptions through unconditional structured cleanup. Process restart creates a fresh coordinator; durable state, not an old lock, determines recovery.
- Locks have no stale timeout and are never stolen. Provider clients enforce bounded connection and operation timeouts. A watchdog may log an unusually long run but cannot authorize overlap.

### Public idempotency and request retry rules

- Keep issue 05's public contract unchanged: no `Idempotency-Key` header, no client operation ID, no polling route, and no automatic POST retry in the generated client or either consumer adapter.
- A user may explicitly repeat a POST after a known failure or uncertain network outcome. The backend always re-enters through the same domain-key checks and recovery rules; the browser never assumes that a disconnected request failed before effects.
- Capture's public idempotency key is canonical Job URL. Under URL exclusion, zero complete active matches permits creation, one complete active match returns `already_captured`, and multiple complete active matches produce `409 conflict` for manual workspace repair.
- Application Analysis run requests are not idempotent as a batch. Each selected Application is semantically repeatable because a complete selected Application Analysis section is the durable body marker and final properties are repairable.
- Resume Creation's public idempotency key is Application ID plus the active final Application-to-Job-Specific-Resume relation. Exactly one completed active Resume returns `already_created`; multiple active completed Resumes are an integrity conflict.
- GET retries remain bounded to network failures in consumer-owned policy. Invalid or stale cursors reset to page one and are not replayed unchanged.
- DeepSeek retry rules remain two bounded transport retries for explicitly retryable failures plus at most one structured-output repair call. All model attempts finish before the first durable workflow effect.
- Notion reads and queries may use bounded retry with backoff for timeouts, rate limits, connection resets, and retryable server failures.
- Target-state writes that are idempotent by resource ID, including final property patches, relation clearing, archival, and equivalent cleanup operations, may use bounded retry after rereading when necessary.
- Page creation and block append are not retried automatically after an ambiguous timeout because replay could create duplicate pages or sections. They enter reconciliation with the last confirmed journal phase and workspace evidence.
- PDF generation writes to a temporary file in the Merida-owned export root, flushes and closes it, and atomically replaces the opaque final filename. Repeating publication for the same journal-owned Resume ID is safe; arbitrary paths are never accepted.

### Effect journal and recovery authority

- Add one feature-neutral persistence interface named `EffectJournal`, but keep interpretation and recovery policy in Capture and Resume Creation. The journal is a narrow durability mechanism, not a generic saga framework.
- The real local implementation is a versioned, validated, atomically replaced JSON document under the configured Merida data root. Tests use an in-memory or fault-injecting implementation behind the same interface.
- Each active entry contains only schema version, run ID, workflow, domain key hash or safe canonical identifier, phase, created Notion page IDs, opaque PDF artifact ID, start/update timestamps, cleanup status, safe cleanup codes, and resolution status.
- Journal entries never contain Job Content, Captured HTML, Company or Role text unless needed as an already-public safe label, Master Resume evidence, analysis or resume bodies, prompts, model output, credentials, headers, database IDs, Notion payloads, raw provider errors, or filesystem paths.
- A journal entry is created and durably published before the workflow's first external effect. It advances only after an effect is confirmed. The small unavoidable window between a provider accepting a create and returning its identifier is treated as ambiguous provider state, not falsely described as exactly-once execution.
- Completed entries may be compacted after a bounded retention period once the domain completion marker is reread successfully. Unresolved and manual-recovery entries are never removed by ordinary compaction.
- Journal parsing or schema failure blocks Capture confirmation and Resume Creation mutations. The backend preserves the unreadable journal for inspection and does not replace it with an empty document. Readiness and safe diagnostics explain the recovery requirement without returning its raw contents.
- Startup performs bounded reconciliation before enabling Capture confirmation and Resume Creation. Reconciliation may also run lazily for the exact domain key before a repeated mutation. It does not scan or rewrite the entire Notion workspace.
- Unresolved recovery for one canonical Job URL or Application ID blocks that key. Unrelated keys remain available unless the journal itself is unreadable or a global adapter capability is unsafe.
- Application Analysis does not use the effect journal in v1. Its complete stable body section and final properties contain enough durable evidence for repair, while an extra journal would duplicate private workflow lifecycle without closing a unique crash window.

### Capture recovery

- Capture writes a journal intent after canonicalization, readiness, duplicate lookup, and URL exclusion, but before creating an Application page.
- After Application creation returns, the journal records its page ID before additional body effects. Successful completion requires a complete readable Capture Summary and Job Content plus the default Application properties.
- A normal create or append failure attempts to archive the page only when the current journal entry proves that the run created it. Successful archival produces a technical failure with cleanup completed; the operator may explicitly retry.
- On restart, a journal-owned active page with a complete Capture Summary and Job Content is treated as completed and returned by the next confirmation as `already_captured`.
- A journal-owned page with incomplete body effects and no evidence of later operator adoption is archived automatically, then the entry is resolved so an explicit retry may create a replacement.
- If archival fails, cleanup becomes incomplete and the canonical URL is blocked for manual recovery. Merida does not create another active Application beside known residue.
- An active incomplete page found only by URL, without a journal entry proving ownership, is ambiguous. Merida returns `409 conflict` and never archives it automatically. The operator resolves it in Notion or explicitly authorizes resolution through the maintenance command.
- Multiple active exact-URL matches are always manual workspace recovery. Merida does not select, merge, relate, or archive an arbitrary duplicate.
- The prepare-time metadata cache remains best-effort and non-durable. Confirmed reviewed values and Job Content are authoritative. After restart, optional Captured URL provenance may fall back to the canonical Job URL rather than making confirmation unsafe or adding a new public preparation token.

### Application Analysis recovery

- Only one Analysis batch may select work at a time. It obtains the current eligible queue after acquiring the batch gate; it never resumes a persisted or pre-lock batch list after restart.
- Before each item, the workflow acquires the Application key, reloads the Application, and revalidates status, Job Content, current analysis body, and final properties. An item that became ineligible is returned as `skipped` with a safe reason and receives no model call or write.
- `processed` equals the number of returned item results. `succeeded` counts `analyzed` and `repaired`; `failed` counts only `failed`; `repaired` is the subset of succeeded items with result `repaired`; skipped count is derived from the item list. Thus `processed = succeeded + failed + skipped`.
- A complete selected canonical or legacy analysis section with incomplete final properties is repaired without a model call. Its persisted Match Score is authoritative when present; the accepted deterministic legacy recomputation rule applies only when the selected legacy body lacks a score.
- A complete canonical body and final properties form completed analysis even if an interrupted trailing section exists. The compatibility adapter's last-complete-section selection remains authoritative and no sections are merged.
- If no complete recognized section exists, Merida does not set `Analyzed=true`. A known append failure is reported for that item; a later run may append a fresh complete canonical section while leaving incomplete historical blocks untouched.
- Final property updates are idempotent target-state writes and may be retried safely. A crash after body append but before property finalization is repaired by the next batch without another DeepSeek call.
- An Application with `Analyzed=true` but no complete readable analysis is a workspace integrity block requiring manual Notion repair. Merida never treats the checkbox alone as proof of completed analysis.
- Per-item exceptions remain isolated. The Application key is released before the next item, and one failed or skipped item does not release the batch gate early or abort subsequent items.

### Resume Creation commit and recovery

- Resume Creation acquires the global Resume gate and Application key before revalidating eligibility, unresolved journal state, completed Resume relations, Master Resume evidence, and all generation guards.
- No journal entry and no artifact effect are created until model generation and deterministic evidence validation have completed successfully.
- The commit order remains: create an unlinked Job-Specific Resume, atomically publish its PDF from the same validated Resume Document, create the Resume Fit Analysis Note with its required Application and Resume relations, then attach the Resume to the Application last.
- The journal records each confirmed artifact ID immediately after its effect. The final relation is the durable completion marker; the journal is supporting recovery evidence, not an alternative definition of success.
- A caught failure compensates confirmed effects in reverse order: clear a possibly attempted final relation, archive the journal-owned Note, remove the journal-owned PDF, and archive the journal-owned Resume. Missing artifacts during cleanup count as already absent, not cleanup failures.
- Cleanup operates only on exact identifiers recorded by the journal and verifies expected artifact kind and relation context before destructive effects. It never searches by a human-readable title and archives the first match.
- A fully compensated request returns the existing `failed` result with cleanup status `completed`. Any unconfirmed, ambiguous, or failed cleanup effect returns cleanup status `incomplete`, persists the recovery entry, and blocks the Application key.
- On restart, reconciliation first rereads the Application's active Resume relations. If the journal-recorded Resume is the single completed relation, the run is marked completed and its artifacts are preserved even if the process stopped before journaling completion.
- If no final relation exists, reconciliation compensates only recorded and verified artifacts in reverse order. After complete cleanup, a later explicit request may start a new run.
- If a different completed Resume relation now exists, multiple completed relations exist, a recorded artifact cannot be verified, or an unrecorded orphan is suspected, reconciliation stops and requires manual recovery.
- The unavoidable create-response crash window may leave an unjournaled unlinked Resume. V1 does not perform broad automatic orphan scans or title-based deletion. The maintenance command may present redacted candidates by creation time and safe identifiers, but the operator must explicitly choose any archive action.
- `already_created` remains truthful even when a historical completed Resume lacks a discoverable Note or PDF. Missing-PDF and historical-artifact repair stay outside this issue.

### Manual recovery and operational boundary

- Provide a backend-local maintenance command with three capabilities: inspect unresolved entries, retry safe reconciliation for one entry, and acknowledge operator-completed recovery. It uses the same settings, adapters, validation, journal, and safety checks as the application.
- The command defaults to read-only inspection. Any archival, relation clearing, PDF removal, or resolution acknowledgement requires an explicit entry identifier and confirmation. It never accepts arbitrary Notion database IDs, arbitrary page queries, or filesystem paths.
- Inspection prints workflow, run ID, safe domain identifier, phase, artifact IDs needed for Notion lookup, timestamps, cleanup codes, and recommended next action. It redacts private bodies, credentials, raw provider responses, and local paths.
- Acknowledgement does not claim cleanup occurred. It records that the operator resolved or accepted the state and requires a fresh domain revalidation before the workflow key is enabled.
- Normal HTTP routes expose no journal listing, force-unlock, force-cleanup, retry-cleanup, or arbitrary archive endpoint. Notion remains the record-management surface and local CLI access remains an operator procedure.
- Runbooks distinguish four outcomes: completed marker found, automatic cleanup completed, automatic cleanup incomplete, and ambiguous/manual recovery. They never instruct the operator to delete data solely from a title match.

## Testing Decisions

- A good recovery test asserts public HTTP status and typed outcome, final Notion-visible semantic state, published PDF visibility, journal state, safe logs, and cleanup residue. It does not assert the concrete lock class, dictionary keys, private helper call counts, JSON formatting, or LangGraph node order.
- The single highest acceptance seam is the FastAPI ASGI application composed with deterministic fake Notion, model, PDF, journal, clock, and barrier adapters. Tests issue genuinely overlapping requests through the ASGI client and coordinate them at semantic effect barriers.
- Reconstructing a new app instance over the same fake durable workspace, PDF store, and journal is the restart seam. Tests must not preserve the old coordinator or workflow instances across the simulated restart.
- Coordinator contract tests cover one Analysis batch, one Resume mutation, same-URL Capture exclusion, different-URL Capture concurrency, shared per-Application exclusion, fail-fast conflict, fixed acquisition order, cancellation release, and demo-reset exclusivity.
- Public-contract tests cover `409 conflict` for overlapping Analysis, Resume, reset, and unsafe ambiguous state without changing the locked OpenAPI response envelope or adding idempotency headers.
- Capture tests overlap two confirmations for the same canonical URL and prove exactly one active Application plus created/already-captured outcomes. URL variants, ambiguous duplicate matches, known partial pages, failed archival, restart reconciliation, and best-effort prepare metadata are covered.
- Analysis tests overlap two run requests, mutate eligibility between queue selection and item lock, and verify count reconciliation for analyzed, repaired, skipped, and failed items.
- Analysis crash tests inject failure after model output, during body append, after complete body append, and during final property update. They prove no effects before validation, no unsafe append retry, repair without a model call, no checkbox-only completion, and continued per-item isolation.
- Resume tests inject failure or process interruption before and after journal intent, Resume creation, PDF publication, Note creation, final relation attempt, final relation success, and journal completion.
- Every Resume crash test restarts the app and proves either preserved completion, complete reverse cleanup, or a persisted manual-recovery state. It also proves that cleanup never touches an artifact not recorded and verified for that run.
- Compensation tests cover relation-clear failure, Note archival failure, PDF removal failure, Resume archival failure, already-missing artifacts, multiple simultaneous cleanup failures, and a successful later reconciliation attempt.
- Provider retry tests prove bounded read retries, idempotent target-state retry, no automatic ambiguous page-create or block-append retry, disabled nested DeepSeek retries, and no model retry after persistence begins.
- PDF tests prove temporary files are not downloadable, final publication is atomic, repeated journal-owned publication is deterministic, removal is restricted to the validated export root, and public responses never expose local paths.
- Journal tests cover schema versioning, atomic replacement interruption, corrupt content, unknown future version, compaction, unresolved-entry retention, privacy exclusions, domain-key isolation, and safe concurrent updates.
- Maintenance-command tests prove read-only defaults, explicit targeting and confirmation, safe reconciliation reuse, revalidation after acknowledgement, refusal of arbitrary IDs or paths, and redacted output.
- Privacy tests inspect HTTP responses, generated OpenAPI, structured logs, exceptions, journal documents, and command output for forbidden Job Content, Master Resume evidence, generated bodies, prompts, model output, tokens, database IDs, raw Notion payloads, and filesystem paths.
- Demo and real-store conformance suites run the same domain idempotency, effect-order, compensation, and restart scenarios. The real Notion suite uses deterministic transport recordings and fault injection; no private workspace or live provider is required by the root gate.
- Existing prior art includes the ASGI public-contract tests, CaptureStore canonical-URL tests, ApplicationAnalysisStore body-first/property-second repair tests, ResumeArtifactCommitter effect-order and reverse-cleanup tests, demo atomic-state tests, and versioned prototype parity scenarios.
- Completion requires the root final-app verification gate to pass without credentials or network calls and a manual real-provider smoke run to confirm Notion timeout classification and archive/relation behavior before real mode is enabled.

## Out of Scope

- Durable LangGraph checkpoints, graph replay, human interruption inside a graph, or persistence of graph state, prompts, Job Content, Master Resume evidence, or model output.
- Distributed locks, Redis, a database-backed lease service, background workers, task queues, multi-process ASGI workers, multiple Merida server instances, cloud deployment, or cross-machine execution.
- Client-provided idempotency keys, request polling, background job IDs, automatic POST retries, WebSockets, SSE, NDJSON, or streamed recovery progress.
- Exactly-once guarantees across Notion or filesystem failures. V1 provides process-local exclusion, semantic idempotency, durable effect evidence, bounded reconciliation, and explicit ambiguity.
- Renaming or adding Notion databases, properties, select options, or relations. The journal is local backend metadata and does not become a new Notion schema.
- A generic transaction, saga, unit-of-work, repository, or workflow engine shared across unrelated features.
- Automatic deletion of ambiguous, operator-authored, title-matched, or unjournaled Notion records.
- Historical duplicate merging, missing-PDF repair, missing-Note repair, general orphan discovery, arbitrary artifact browsing, or general Notion cleanup.
- Changing the locked `/api/v1` routes, request models, response unions, generated client surface, capture-token policy, CORS policy, or queue pagination contract.
- Changing model prompts, evidence guardrails, deterministic Match Score or Fit Score behavior, Application Status rules, queue eligibility, or artifact content.
- Adding progress UI, a recovery dashboard, a record editor, or cleanup controls to `/dashboard` or the Chrome extension.
- Prototype retirement, final cutover timing, release packaging, installation, or supported-platform policy.

## Further Notes

- Process-local locks deliberately match the accepted one-process local runtime. They are sufficient only because startup rejects multi-worker execution and real mode remains disabled until the full recovery suite passes.
- The effect journal is intentionally smaller than a checkpointer: it records external-effect ownership and phase, not workflow inputs or resumable computation. After a crash, Merida either recognizes a durable completion marker or compensates; it reruns computation only through a new explicit request.
- Notion cannot provide a cross-page transaction or unique constraint for canonical Job URL. The spec therefore states exactly where v1 is strongly protected and where an ambiguous provider response or out-of-band edit requires operator judgment.
- If future deployment requires multiple workers or machines, replace the execution coordinator and journal with a durable lease and transactional operation store behind the same workflow-facing concepts, then reopen the public conflict and observability contract as needed.

## Answer

V1 uses one FastAPI worker, fail-fast workflow gates, canonical-URL Capture
exclusion, and shared per-Application exclusion. Public idempotency remains
domain-based with no client key or automatic POST retry. Application Analysis
recovers from its stable body-first Notion marker; Capture and Resume Creation
use a minimal content-free local effect journal in addition to their domain
markers. Resume effects commit relation-last and compensate in reverse. Restart
reconciliation preserves completed work, removes only journal-owned residue,
and escalates ambiguous or incomplete cleanup to an explicit local maintenance
command. The ASGI application with deterministic overlap, fault, and restart
adapters is the authoritative acceptance seam.
