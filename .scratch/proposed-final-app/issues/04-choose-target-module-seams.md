# Choose the target module seams and ownership model

Type: grilling
Status: resolved
Blocked by: 01
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

What deep-module boundaries, public interfaces, and dependency directions should own Applications, Job Postings, Capture, Application Analysis, Matching, Resume Creation, Notes, workspace access, LLM integration, and artifact commit behavior without recreating either a shallow service layer or one oversized `Workspace` interface?

## Problem Statement

The earlier proposal correctly called for deep modules but distributed pursuit
behavior under Job Postings, exposed legacy streaming and direct-capture
operations, passed provider mechanics into workflows, and gathered unrelated
workspace behavior into one broad interface. That shape would make FastAPI
routes thin while merely moving complexity into shallow modules and a growing
`Workspace` abstraction.

## Solution

Organize the target backend around three deep workflow modules—Application
Capture, Application Analysis, and Resume Creation—with consumer-owned store and
model interfaces. Keep Applications as the pursuit owner, Job Postings as the
source-opportunity owner, Matching as a deterministic shared leaf, Notes as a
narrow document module, and artifact commit as an internal Resumes module.
Adapters depend inward on these interfaces and are selected only by the FastAPI
composition root.

## Implementation Decisions

### Workflow-owned workspace interfaces

Each workflow depends on its own narrow semantic workspace interface rather than
one global `Workspace` interface:

- Capture depends on a `CaptureStore` interface.
- Application Analysis depends on an `ApplicationAnalysisStore` interface.
- Resume Creation depends on a `ResumeCreationStore` interface.

The real Notion adapter and the demo adapter may implement all three interfaces,
but they are assembled at the FastAPI composition root and passed to each
workflow through only the interface that workflow is allowed to use. Workspace
interfaces expose domain operations rather than Notion CRUD, schema payloads, or
physical property names.

This keeps workflow rules local, prevents callers from learning unrelated
workspace behavior, and makes each workflow interface the natural test seam.

### Application and Job Posting ownership

`Applications` is the central pursuit module. It owns the Application lifecycle,
eligibility, status, Capture orchestration, Application Analysis orchestration,
and the one-to-one association with the source Job Posting in v1.

`Job Postings` owns source-opportunity information and behavior: Job Content,
source and canonical URLs, company, title, location, and parsing. It does not own
pursuit state or downstream workflow orchestration.

`Resumes` continues to own Resume Creation and reads the Application through a
narrow workflow interface. The Notion adapter maps the unchanged physical Job
Postings database onto the canonical Application and Job Posting model; physical
database names do not determine module ownership.

### Review-first Application Capture

Capture is one deep `ApplicationCapture` module with two public operations:

- `prepare(evidence)` parses and validates Capture Evidence without writing and
  returns a reviewable draft.
- `confirm(draft)` revalidates the operator-corrected fields, detects duplicates,
  and creates or returns the Application.

Job Posting parsing, URL canonicalization, confidence evaluation, duplicate
detection, and workspace writes remain hidden inside the module. The target
interface does not expose direct `capture(evidence)` behavior because Quick
Capture is outside v1 and the selected interaction is review-first.

### Application Analysis

One deep `ApplicationAnalysis` module owns both eligible queue reads and bounded
execution:

- `get_queue(query)` returns eligible Applications, the total eligible count,
  and an opaque next cursor.
- `run_batch(limit)` processes a bounded batch sequentially and returns one final
  typed summary.

The module hides eligibility, input loading, LLM requests, evidence validation,
deterministic Match Score calculation, persistence ordering, partial-write
repair, and per-Application failure isolation. It does not expose an event
emitter or streaming interface. React owns pending presentation while the
workflow and HTTP route return one final result.

### Resume Creation

One deep `ResumeCreation` module owns the eligible queue and one-at-a-time
creation:

- `get_queue(query)` returns eligible Applications, the total eligible count,
  and an opaque next cursor.
- `create(application_id)` returns a typed `created`, `already_created`, or
  `failed` outcome for exactly one Application.

The module hides eligibility revalidation, Master Resume loading, requirement
matching, fit scoring, LLM generation, claim validation, Resume and Note writes,
PDF export, final attachment, and compensation of partial effects. Its canonical
input is an Application identifier rather than a legacy Notion Job Posting page
identifier.

### Deterministic Matching

One shared deterministic `Matching` module serves the two real callers,
Application Analysis and Resume Creation, through a small interface equivalent
to:

`match(targets, evidence_items, scoring_policy) -> MatchResult`

Matching owns normalization, candidate ranking, Evidence Strength
classification, weighted scoring, gaps, category coverage, and scoring-policy
versions. Applications maps Skill Signals into matching targets and owns Match
Score. Resumes maps Fit Requirements into matching targets and owns Fit Score
and the generation gate. Matching has no dependency on Applications, Resumes,
Notion, LLM providers, or HTTP.

### Workflow-specific model interfaces

Workflows depend on task-specific model interfaces instead of a generic prompt
client:

- `ApplicationAnalysisModel.analyze(job_content)`
- `FitRequirementModel.extract(job_content, analysis)`
- `ResumeDraftModel.generate(validated_input)`

A shared DeepSeek structured-output adapter implements these interfaces using
private provider infrastructure. Deterministic demo adapters implement the same
interfaces without provider calls. Prompts, model names, provider schemas,
retries, and raw responses remain hidden; workflows receive typed domain
results and do not call `request_json(prompt, schema, model)` directly.

### Notes ownership

`Notes` is a narrow document module rather than a general CRUD or workflow
module. For v1 it exposes behavior equivalent to:

`create_resume_fit_analysis_note(fit_analysis, claim_traces) -> NoteDocument`

Notes owns the durable Resume Fit Analysis Note structure, headings, evidence
presentation, and safe rendering rules. Resume Creation owns when the Note is
created, and `ResumeCreationStore` persists it as part of the Resume artifact
commit sequence. General Notes management remains outside the app.

### Resume artifact commit

`Resumes` owns an internal deep `ResumeArtifactCommitter` module with an
interface equivalent to:

`commit(validated_bundle) -> ArtifactCommitResult`

It creates an unlinked Resume draft, exports the PDF from the same validated
Resume Document, creates the unlinked Resume Fit Analysis Note, adds required
Note and Resume relations, and attaches the final Resume-to-Application relation
last. If an effect fails, it compensates completed effects in reverse order and
reports cleanup results explicitly.

This is a feature-owned commit module, not a generic transaction framework.
`ResumeCreation` is its only production caller.

### Dependency direction

Dependencies point inward from adapters to workflow modules and from workflow
modules to consumer-owned semantic interfaces and domain values:

```text
FastAPI routers and React clients
              -> workflow modules
              -> consumer-owned interfaces and domain values
              <- Notion, DeepSeek, demo, PDF, and filesystem adapters
```

- Applications does not depend on Resumes.
- Resume Creation reads an Application through `ResumeCreationStore`; it does
  not call Application Analysis.
- Applications and Resumes may both depend on the leaf Matching module.
- Resumes may depend on the narrow Notes document module.
- Workflows do not import FastAPI, the Notion SDK, DeepSeek transport,
  filesystem paths, or demo fixtures.
- The FastAPI composition root selects and injects adapters.

## Testing Decisions

- Versioned parity scenarios exercise `ApplicationCapture`,
  `ApplicationAnalysis`, and `ResumeCreation` through their public interfaces.
- Notion and demo adapters run the same behavioral conformance suite for each
  narrow store interface; there is no global Workspace conformance suite.
- Matching fixtures cover both Skill Signal-to-evidence Match Score and Fit
  Requirement-to-evidence Fit Score without importing either caller.
- Real DeepSeek and deterministic demo adapters satisfy the same task-specific
  model contracts.
- Resume artifact tests assert the ordered effect trace, forbidden premature
  attachment, reverse compensation, and explicit cleanup residue.
- Router tests stop at validated requests and final typed responses; they do not
  test workflow behavior through FastAPI internals or a streaming transport.

## Out of Scope

- Exact REST paths, Pydantic DTOs, error envelopes, auth dependencies,
  pagination encoding, and generated TypeScript names.
- Exact legacy Notion property mapping and the concrete operation set required
  by each store adapter.
- Python and TypeScript package roots, build tooling, process lifecycle, and
  repository topology.
- Locking, idempotency keys, crash recovery, demo persistence, and cutover
  sequencing.
- General Notes CRUD, Quick Capture, batch Resume Creation, or a generic
  transaction framework.

## Further Notes

- Exact store operation names may be refined by the Notion compatibility
  decision, but that work must not widen the workflow interfaces into Notion
  CRUD or merge them into one Workspace interface.
- Exact HTTP schemas may adapt these module results, but routes must not add
  workflow behavior or reintroduce streaming into Application Analysis.
- Physical repository placement remains provisional until the runtime and
  repository-topology decision is resolved.

## Answer

The target ownership and dependency model is settled above. Applications owns
pursuit workflows; Job Postings owns source-opportunity behavior; Resumes owns
Resume Creation and its internal artifact committer; Notes owns the Resume Fit
Analysis Note document; and Matching is a shared deterministic leaf. Each
workflow receives only its own semantic store and task-specific model
interfaces, with Notion, demo, DeepSeek, PDF, and filesystem details supplied by
inward-pointing adapters at the FastAPI composition root.
