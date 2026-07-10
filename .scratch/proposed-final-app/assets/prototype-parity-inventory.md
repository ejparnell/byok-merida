# Merida Prototype Parity Inventory

Contract version: `prototype-parity-v1`  
Fixture schema: `1`  
Machine-readable corpus: `test/parity/fixtures/prototype-parity.v1.json`  
Executable prototype harness: `test/parity/prototypeHarness.js`

## Purpose

This inventory separates observable prototype behavior that defines migration parity from behavior intentionally replaced by the reviewed final-app contracts. It is a cutover reference, not a requirement to preserve the prototype's Node modules, backend-rendered HTML, route names, NDJSON transport, long-running Python sidecar, or exact response fields.

The public workflow seam is:

```text
canonical initial state
  + action
  + deterministic boundary responses
  -> typed outcome
  + semantic workspace and artifact effects
  + ordered safety-critical effect trace
  + cleanup residue
```

The executable harness calls the prototype's public Capture, Application Analysis, and Resume Creation interfaces. Recording fakes replace only system boundaries such as Notion, DeepSeek, time, and PDF storage. Capture Evidence normalization remains one narrow supporting seam before the backend workflow boundary.

## Authority Rules

1. The working prototype, its focused tests, current docs, and accepted ADRs establish current observable behavior.
2. The reviewed final-app route, frontend, extension, Notion schema, and AI workflow contracts establish intentional replacements and target additions.
3. The Wayfinder map preserves existing Notion data and physical schema, even where canonical Application vocabulary differs.
4. A conflict is recorded below; it is not silently resolved by treating an older proposed document as authoritative.
5. Exact module, API, adapter, runtime, concurrency, demo, and roadmap decisions remain with their owning tickets.

## Versioned Fixtures

| Fixture ID | Classification | Contract |
| --- | --- | --- |
| CAPTURE-EVIDENCE-001 | `parity_required` | Normalize multi-frame evidence, canonicalize the Job URL, prefer selected text, and retain structured JobPosting metadata. |
| CAPTURE-001 | `parity_required` | Return `already_captured` for a canonical Job URL duplicate without creating another Application. |
| CAPTURE-002 | `parity_required` | Parse strong Capture Evidence for review without reading or writing the workspace. |
| CAPTURE-003 | `parity_required` | Exercise Capture creation, review, missing-content, invalid-schema, confirmation, Capture Defaults, and stable body persistence. |
| ANALYSIS-001 | `parity_required` | Process a sequential batch after one item fails and persist the later valid item. |
| ANALYSIS-002 | `parity_required` | Repair the analysis marker from an existing body without another model call or duplicate body write. |
| ANALYSIS-003 | `parity_required` | Validate evidence-backed analysis output and prove body-first partial persistence when the final property commit fails. |
| ANALYSIS-004 | `parity_required` | Capture the prototype's `To Apply` plus unanalyzed queue filter and bounded query, while marking readable-content eligibility and the `1..10` limit as target changes. |
| ANALYSIS-ADD-001 | `target_addition` | Persist deterministic Match Score in the body and property so repair can recover the exact value. |
| RESUME-001 | `parity_required` | Block insufficient Master Resume evidence before Resume, Note, PDF, or relation effects. |
| RESUME-002 | `parity_required` | Return the existing Resume before generation or artifact work; target result name is `already_created`. |
| RESUME-003 | `parity_required` | Prove missing sources, ambiguous Master Resume state, empty evidence, and too-few role bullets all fail before artifacts. |
| RESUME-004 | `parity_required` | Reject an invented cross-role claim, preserve role chronology, and fill every role only from its own Master Resume evidence. |
| ARTIFACT-001 | `parity_required` | Produce an employer-facing Resume, related Resume Fit Analysis Note, PDF, and durable final attachment. |
| CLEANUP-001 | `parity_required` | Remove the PDF and archive the Note and Resume draft when final attachment fails. |
| CLEANUP-002 | `parity_required` | Prove actual state residue after injected Note, PDF, and final-attachment failures. |
| PRIVACY-001 | `parity_required` | Keep Notion and DeepSeek credentials owned by backend environment configuration. |
| PRIVACY-ADD-001 | `target_addition` | Keep prompts, credentials, private source content, raw model output, and local paths out of normal logs and responses. |
| NOTION-001 | `parity_required` | Preserve legacy physical properties, stable body sections, database/data-source relation targets, and inverse relation validation. |
| TRANSPORT-001 | `superseded` | Replace analysis NDJSON and backend HTML with dashboard pending state and one final typed response. |
| EXTENSION-DEFECT-001 | `known_defect` | Do not preserve the missing result element that the current result renderer dereferences. |
| API-DEFERRED-001 | `deferred` | Leave exact target HTTP schemas and generated client naming to the public API client contract ticket. |
| SUPERSEDED-001 | `superseded` | Replace legacy pages, routes, NDJSON, batch range, and queue leakage with reviewed target surfaces. |
| SUPERSEDED-002 | `superseded` | Replace fixed Resume templates, old score/result/path contracts, sidecar topology, prompt slicing, and private logging. |
| TARGET-ADD-002 | `target_addition` | Add canonical Resume rendering, unchanged non-work sections, shared PDF/Notion source, and typed cleanup state. |
| DEFECT-002 | `known_defect` | Do not freeze contradictory direct-capture documentation or the unused `skipped` result. |
| WAYFINDER-DEFERRED-001 | `deferred` | Route module, Notion mapping, runtime, recovery, demo, and roadmap decisions to their owning tickets. |

## Capture Inventory

| Observable behavior | Classification | Evidence or fixture | Final-app disposition |
| --- | --- | --- | --- |
| Merge active-tab and readable frame URL, title, selected text, visible text, semantic HTML, and metadata. | `parity_required` | CAPTURE-EVIDENCE-001 and current Capture Evidence tests. | Preserve behind the extension's Active Tab Evidence and Capture Evidence interfaces. |
| Prefer deliberate selected text; otherwise fall back to readable visible, HTML, and metadata content. | `parity_required` | CAPTURE-EVIDENCE-001 and parser tests. | Preserve. |
| Remove obvious tracking parameters from the canonical Job URL while preserving job-identifying parameters and the Captured URL. | `parity_required` | CAPTURE-EVIDENCE-001, URL tests, and Capture context. | Preserve canonical duplicate semantics and source provenance. |
| Reject oversized unbounded evidence by applying documented limits and warnings. | `parity_required` | CAPTURE-EVIDENCE-001 and focused Capture Evidence limits test. | Preserve with a versioned payload limit. |
| Parse for review without Notion schema validation, duplicate lookup, or workspace writes. | `parity_required` | CAPTURE-002. | Preserve on `POST /applications/parse`. |
| Create a high-confidence record only after schema validation and canonical duplicate lookup. | `parity_required` | CAPTURE-003 and Capture service tests. | Preserve semantic order; exact HTTP shape is deferred. |
| Return `needs_review` for incomplete or low-confidence evidence without creating a record. | `parity_required` | CAPTURE-003. | Preserve as an expected product outcome. |
| Return the existing record for a canonical duplicate. | `parity_required` | CAPTURE-001. | Preserve as `already_captured`, not an error. |
| Block missing Job URL, missing readable Job Content, invalid schema, and failed writes without a completed record. | `parity_required` | CAPTURE-003. | Preserve; validation failures remain actionable. |
| Confirmation revalidates reviewed fields, canonicalizes the Job URL, checks duplicates, and creates once. | `parity_required` | CAPTURE-003. | Preserve on `POST /applications/confirm`. |
| Successful Capture writes a stable Capture Summary and readable Job Content. | `parity_required` | CAPTURE-003. | Preserve semantic sections. |
| Successful Capture sets `Application Status = To Apply`, leaves analysis false, and leaves Match Score and application dates empty. | `parity_required` | CAPTURE-003. | Preserve as Capture Defaults. |
| The prototype treats Location as a minimum creation field. | `superseded` | SUPERSEDED-001. | The reviewed extension contract makes Location optional; Company Name, Role, Job URL, and readable Job Content remain required. |
| Direct Capture is described in current docs but absent from the executable side-panel action surface. | `known_defect` | DEFECT-002. | Review-first **Fill Form** is primary; Quick Capture remains optional. |

## Application Analysis Inventory

| Observable behavior | Classification | Evidence or fixture | Final-app disposition |
| --- | --- | --- | --- |
| Select only `To Apply`, unanalyzed work and process a bounded batch sequentially. | `parity_required` | ANALYSIS-004 and ANALYSIS-001. | Preserve sequential item graphs; reviewed limit is `1..10`. |
| Continue after one item fails and return exact per-batch totals. | `parity_required` | ANALYSIS-001. | Preserve failure isolation in one final response. |
| Read only the stable Job Content section as the analysis source. | `parity_required` | ANALYSIS-003. | Preserve; Capture metadata and prior analysis are not model input. |
| Require exactly three non-empty summary sentences. | `parity_required` | ANALYSIS-003. | Preserve. |
| Require evidence-backed Skill Signals, reject unsupported evidence, drop generic traits, and merge normalized duplicates. | `parity_required` | ANALYSIS-003. | Preserve and map into canonical Application Analysis models. |
| Append the analysis body before committing final properties. | `parity_required` | ANALYSIS-003. | Preserve body-first/property-final safety. |
| Repair an existing readable analysis body without another model call or duplicate append. | `parity_required` | ANALYSIS-002. | Preserve and recover exact Match Score when stored. |
| Calculate Match Score deterministically from validated Skill Signals and Master Resume evidence. | `target_addition` | ANALYSIS-ADD-001 and reviewed AI contract. | Required before target cutover; the LLM never supplies the final score. |
| Store the same Match Score in the analysis body and property. | `target_addition` | ANALYSIS-ADD-001. | Required for exact repair. |
| Queue a record without readable Job Content, then fail it during the batch. | `superseded` | SUPERSEDED-001 and ANALYSIS-004. | Target queues are eligible-only; unreadable records stay out and are fixed in Notion. |
| Clamp analysis batches to `1..25`. | `superseded` | SUPERSEDED-001 and ANALYSIS-004. | Reviewed dashboard and route contract clamps to `1..10`. |
| Stream `run_started`, item events, and `run_finished` over NDJSON. | `superseded` | TRANSPORT-001. | Target returns one final typed batch response. |
| Declare a `skipped` result without an observable execution path. | `known_defect` | DEFECT-002. | Do not freeze `skipped` until a concrete product condition owns it. |

## Resume Creation Inventory

| Observable behavior | Classification | Evidence or fixture | Final-app disposition |
| --- | --- | --- | --- |
| Reload and revalidate the selected Application rather than trusting queue preview state. | `parity_required` | RESUME-003. | Preserve. |
| Return an existing related Resume before schema, model, Note, or PDF work. | `parity_required` | RESUME-002. | Preserve; normalize result name from `already_exists` to `already_created`. |
| Require readable Job Content and analysis, exactly one Master Resume, and extractable evidence. | `parity_required` | RESUME-003. | Preserve using canonical Application Analysis while reading legacy bodies compatibly. |
| Validate Fit Requirement evidence against Job Content before scoring. | `parity_required` | RESUME-001. | Preserve; Application Analysis is supporting structure only. |
| Normalize aliases, rank lexical/TF-IDF candidates deterministically, and classify direct, adjacent, weak, or no evidence. | `parity_required` | RESUME-001. | Preserve under versioned scoring and dictionary policies. |
| Allow targeted claims only from direct or adjacent evidence. | `parity_required` | RESUME-004. | Preserve. |
| Block insufficient evidence before any artifact effect. | `parity_required` | RESUME-001. | Preserve as a typed workflow block. |
| Validate every generated bullet's Evidence IDs, Requirement IDs, role ownership, and source support. | `parity_required` | RESUME-004. | Preserve; one bounded repair attempt is a target contract. |
| Preserve work-experience role chronology and keep evidence inside its source role. | `parity_required` | RESUME-004. | Preserve. |
| Reach five to seven truthful bullets per role or fail before writes. | `parity_required` | RESUME-003 and RESUME-004. | Preserve, with six preferred. |
| Keep employer-facing Resume content separate from the Resume Fit Analysis Note. | `parity_required` | ARTIFACT-001 and related Note ADR. | Preserve. |
| Create Resume, Note, and PDF before the final Resume Attachment. | `parity_required` | ARTIFACT-001 and PDF ADR. | Preserve semantic completion; target strengthens relation staging. |
| Render the Notion Resume and PDF from one canonical validated Resume Document. | `target_addition` | TARGET-ADD-002. | Required to prevent output drift. |
| Preserve contact details and all non-work Master Resume sections unchanged. | `target_addition` | TARGET-ADD-002. | Required; the LLM may not rewrite them. |
| Use four hard-coded Elizabeth-specific roles and contact data as the source template. | `superseded` | SUPERSEDED-002. | Parse identity, roles, chronology, and sections from the actual Master Resume. |
| Represent Fit Score on the prototype's `0..1` scale. | `superseded` | SUPERSEDED-002. | Reviewed public domain score is `0..100`; preserve ordering, classifications, and gate semantics. |
| Return `already_exists`. | `superseded` | RESUME-002. | Return canonical `already_created`. |

## Notion Persistence And Artifact Inventory

| Observable behavior | Classification | Evidence or fixture | Final-app disposition |
| --- | --- | --- | --- |
| Existing physical databases are Job Postings, Resumes, and Notes with legacy property and relation names. | `parity_required` | NOTION-001. | Preserve physical data; project into canonical Application language through the future adapter. |
| Accept current Notion relation targets expressed through database IDs or data-source IDs and validate inverse relation names when available. | `parity_required` | NOTION-001. | Preserve compatibility. |
| Recognize legacy `Job Posting Analysis` bodies for Resume Creation and repair. | `parity_required` | Current body readers and ANALYSIS-002. | Preserve read compatibility even if new target writes use canonical Application Analysis language. |
| Archive Notion drafts instead of claiming hard deletion. | `parity_required` | Resume/Note adapter tests and CLEANUP-001. | Preserve and report `Archived` cleanup fields. |
| On final attachment failure, remove the PDF, archive the Note, archive the Resume, and leave no completed Resume relation. | `parity_required` | CLEANUP-001. | Preserve; target also clears any partial relations explicitly. |
| On Note failure, archive the unlinked Resume; on PDF failure, archive Note and Resume. | `parity_required` | CLEANUP-002. | Preserve as failure-injection cases. |
| Expose `export/{CompanyName}-ElizabethParnell.pdf` and the local relative path. | `superseded` | SUPERSEDED-002. | Use backend-owned storage and return a download URL without a local path. |
| Snapshot exact PDF bytes or model prose. | `superseded` | SUPERSEDED-002. | Assert canonical content and valid artifact metadata, not incidental bytes or wording. |

## Privacy And Observability Inventory

| Observable behavior | Classification | Evidence or fixture | Final-app disposition |
| --- | --- | --- | --- |
| Keep Notion and DeepSeek credentials in backend configuration. | `parity_required` | PRIVACY-001. | Preserve. |
| Exclude prompts, full Job Content, Master Resume content, raw model output, Notion payloads, generated Resume text, auth headers, and local PDF paths from normal logs and responses. | `target_addition` | PRIVACY-ADD-001. | Required target regression suite. |
| Log private Job Content previews during prototype analysis debugging. | `superseded` | SUPERSEDED-002. | Replace with safe counts, IDs, outcome codes, versions, and latency only. |
| Slice prompt payloads by character count. | `superseded` | SUPERSEDED-002. | Select complete typed records before TOON/JSON encoding; never truncate serialized payload text. |

## Known Defects

| Defect | Classification | Target rule |
| --- | --- | --- |
| The side-panel result element is commented out while the result renderer dereferences it. | EXTENSION-DEFECT-001 | Preserve intended created, already-captured, needs-review, and failed states; do not reproduce the missing element. |
| Current docs describe direct Capture while the executable side panel intentionally exposes only Fill Form and confirmation. | `known_defect` | DEFECT-002: treat review-first Capture as authoritative; Quick Capture is optional. |
| `skipped` is declared but has no demonstrated workflow branch. | `known_defect` | DEFECT-002: do not add it to the target contract without a named product condition. |

## Intentionally Superseded Prototype Surfaces

- Separate `/analysis` and `/resumes` HTML pages become the single React `/dashboard` LLM process console.
- Old Capture and Job Posting route names are not compatibility requirements.
- NDJSON analysis progress becomes pending UI plus one final typed response.
- The batch maximum changes from 25 to 10.
- The Node orchestration and long-running Python fit-runtime process split are implementation history.
- Hard-coded Elizabeth-specific Resume roles and contact structure are replaced by Master Resume parsing.
- Local export paths and filenames are replaced by backend-owned PDF download metadata.
- Exact IDs, timestamps, Notion URLs, provider request IDs, model prose, logs, PDF bytes, and internal call graphs are normalized or ignored unless a later contract explicitly stabilizes them.

## Deferred Decisions

| Owner | Deferred question |
| --- | --- |
| API-DEFERRED-001 | Exact public schemas, route prefix, generated TypeScript names, and HTTP status mapping details. |
| Choose the target module seams and ownership model | Final production interfaces and dependency directions. |
| Define the Notion compatibility adapter | Exact legacy-physical to canonical-domain field and heading translation. |
| Choose the runtime repository topology | Runtime packaging, process ownership, and repository layout. |
| Set concurrency, idempotency, and recovery | Simultaneous runs, crash-window behavior, durable journals, and recovery policy. |
| Define demo mode acceptance | Reset, persistence, privacy, and deterministic adapter acceptance. |
| Build the migration roadmap | Vertical slices, cutover gates, ticket order, and prototype retirement. |

## Coverage Audit

| Required area | Covered by |
| --- | --- |
| Capture Evidence | CAPTURE-EVIDENCE-001 plus focused normalization limit tests. |
| Capture | CAPTURE-001, CAPTURE-002, CAPTURE-003, and focused evidence-limit cases. |
| Application Analysis | ANALYSIS-001 through ANALYSIS-004 and ANALYSIS-ADD-001. |
| Resume Creation | RESUME-001 through RESUME-004 and ARTIFACT-001. |
| Notion persistence | CAPTURE-001, ANALYSIS-002, ARTIFACT-001, and existing adapter contract suites. |
| Evidence validation | ANALYSIS-001, ANALYSIS-003, RESUME-001, RESUME-003, and RESUME-004. |
| Artifact creation | ARTIFACT-001. |
| Idempotency | CAPTURE-001, ANALYSIS-002, RESUME-002. |
| Failure cleanup | CLEANUP-001 and CLEANUP-002. |
| Privacy | PRIVACY-001 and PRIVACY-ADD-001. |
| Supersessions | TRANSPORT-001, SUPERSEDED-001, and SUPERSEDED-002. |
| Known defects | EXTENSION-DEFECT-001 and DEFECT-002. |
| Deferrals | API-DEFERRED-001 and WAYFINDER-DEFERRED-001. |

## Cutover Use

- `parity_required` observations must remain green against the frozen prototype and the target implementation after domain normalization.
- `target_addition` observations become mandatory for the target but are not expected to pass against the prototype.
- `superseded` observations document replacement and may become negative target tests.
- `known_defect` observations must never become passing target expectations.
- `deferred` entries must be resolved by their owning tickets before the migration roadmap is declared decision-complete.
