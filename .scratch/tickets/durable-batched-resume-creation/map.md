# Wayfinder: Durable Batched Resume Creation

Labels: wayfinder:map

State: open

## Destination

Produce a ready-for-agent specification and dependency-ordered implementation ticket bundle under `.scratch/` for durable, asynchronous batched Resume Creation. The result should match the durable Application Analysis operator experience where appropriate while defining Resume-specific provider, spend, failure, artifact, and recovery contracts; product implementation is not part of this map.

## Notes

- Use the canonical language in [Resumes](../../../apps/api/merida_api/features/resumes/CONTEXT.md) and preserve the ownership boundaries in [Merida Context Map](../../../CONTEXT-MAP.md).
- Treat [Durable Batched Application Analysis](../../specs/durable-batched-application-analysis.md) and its [implementation ticket bundle](../durable-batched-application-analysis/tickets.md) as prior art, not as authority for Resume-specific model, call-budget, spend, or artifact-recovery values.
- Use `mattpocock-skills:research` for research tickets, `mattpocock-skills:prototype` for prototype tickets, and `mattpocock-skills:grilling` plus `mattpocock-skills:domain-modeling` for human decisions. Work and resolve no more than one ticket per session.
- The Resume Batch Target ranges from 1 through 10. The dashboard control defaults to 5, while every API start request carries the target explicitly. It operates on the server-owned Resume Creation Queue rather than selected dashboard rows.
- The Resume Creation Queue includes only Applications with Match Score at least 70 percent and orders higher scores first.
- A Resume Run snapshots the first `min(eligible queue size, target × 2)` candidates in that order, excluding Applications under active Resume Artifact Quarantine. It evaluates each at most once and backfills after skips, Candidate-Scoped Failures, or an isolated quarantine whose automatic mutation has stopped.
- A Resume Completion requires run-owned Job-Specific Resume, Resume Fit Analysis Note, PDF, and final Resume-to-Application relation artifacts. Same-run recovery may count; an independently existing Resume does not.
- Every Resume Run has a fixed $1.00 authorization-ledger spend ceiling under approved prices. Calls obey the resolved stage-specific Resume Generation Envelope, and every recovery is explicit and counted without silently lowering quality.
- Resume Runs support cancellation, preserve earlier Resume Completions, and process candidates sequentially with at most one Resume provider call in flight. Only one Resume Run is active, while one independent Application Analysis Run may overlap.
- Same-run crash and partial-artifact recovery keyed by Resume Artifact Set ID are in scope. Historical repair of independently existing Resumes with missing Notes or PDFs is not.
- The durable API replaces the synchronous row-level creation contract after dashboard migration; target `1` remains the canonical single-Resume operation.
- When every decision is resolved and no fog remains, hand the map to `mattpocock-skills:to-spec` and `mattpocock-skills:to-tickets`. Publishing those destination artifacts is the handoff beyond wayfinding, not an early child ticket.

## Decisions so far

- [Establish the two-stage Resume Generation Envelope](01-establish-two-stage-resume-generation-envelope.md) — Use Flash/high/8K for Fit Requirements and Pro/high/16K for Drafts, with two dispatch attempts per stage, fixed deadlines, and no fallback.
- [Prove conservative Resume Generation cost bounds](02-prove-conservative-resume-generation-cost-bounds.md) — Reserve each exact rendered call at cache-miss rates; the four-call context-bound maximum is $1.166160 per candidate, with uncertainty kept fully committed.
- [Set the Resume Run Spend Ceiling](03-set-resume-run-spend-ceiling.md) — Cap each run's approved-price authorization ledger at $1.00 with exact call-level reservations, conservative settlement, two-stage readiness, and precise Resume Committed Spend.
- [Define Resume Run source consistency and candidate revalidation](04-define-resume-run-source-consistency.md) — Fix one Master Resume Version per run and one admitted source version per candidate, with stable revalidation before paid work and a full relation-last Completion Gate.
- [Define run-owned artifact identity and same-run recovery](05-define-run-owned-artifact-recovery.md) — Key each candidate's Resume, Note, PDF, and relation commit by one Resume Artifact Set ID, recover verified partial sets forward, and place ambiguity under Resume Artifact Quarantine with evidence-backed exits.
- [Prototype the minimal Resume Run durability boundary](06-prototype-resume-run-durability-boundary.md) — Use one Resumes-owned transaction authority with content-free coordination, three narrowly encrypted recovery checkpoints, conservative call markers, and an atomic Completion seal.
- [Classify Resume Run failures, outcomes, and cancellation](07-classify-resume-run-failures-and-cancellation.md) — Backfill after definitive isolated candidate defects, stop on shared defects, keep artifact quarantine orthogonal, and make cancellation a first-writer scheduling barrier followed by bounded forward recovery, compensation, or quarantine.
- [Define the operator-visible Resume Run contract](08-define-operator-visible-resume-run-contract.md) — Expose retained revisioned Resume Runs and Artifact Sets with idempotent asynchronous commands, independent quarantine discovery, exact spend and result projections, and one coordinated replacement of synchronous Resume Creation.
- [Prototype the durable Resume Batch dashboard](09-prototype-durable-resume-batch-dashboard.md) — Use a Queue + inspector split that keeps server-ordered queue preview and next-run controls separate from the fixed durable run, spend, candidate, cancellation, and artifact state.

## Not yet specified

- The final implementation tracer bullets and their dependency edges cannot be named until the provider, spend, artifact, durability, failure, public-contract, and dashboard decisions expose the correct module seams and migration order.
- The exact regression ownership, operational-readiness changes, documentation updates, and warranted ADRs depend on the selected durable state and public API designs.
- Any additional Resume Artifact Quarantine operator-recovery or provider-approval decision revealed by the durability prototype or provider research will graduate into a child ticket only when its question becomes precise.

## Out of scope

- Product implementation while this Wayfinder map is open.
- Checkbox or explicit-ID selection of visible queue rows.
- Resume Creation for Applications below the 70 percent Resume Match Threshold.
- Historical repair of independently existing Resumes whose Note or PDF was later removed.
- Counting an independently existing Resume toward a new Resume Run's target.
- Parallel Resume candidates, parallel Resume provider calls, multiple active Resume Runs, or queuing a second Resume Run.
- Preventing an independent Application Analysis Run and Resume Run from overlapping.
- Permanently retaining synchronous `POST /resumes/create` as an alternate execution path.
- Silent quality reduction, hidden fallback, uncounted provider transmissions, or model reasoning in operator-visible progress.
- Rolling back earlier Resume Completions after a later failure, spend limit, or cancellation.
- Changing Application Analysis behavior or public contracts.
- Moving completed Resume or Note authority out of Notion.
- A distributed broker, hosted multi-user scheduling, full run-history browsing, or streaming provider output.
