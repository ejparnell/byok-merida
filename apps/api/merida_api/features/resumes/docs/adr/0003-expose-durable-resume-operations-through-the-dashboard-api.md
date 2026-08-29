# Expose durable Resume operations through the dashboard API

The dashboard will operate Resume Creation through durable Resume Run and Resume Artifact Set resources rather than a synchronous row-level request. A client starts one explicitly targeted run with `POST /api/v1/resumes/runs` and a client-generated idempotency key, then reconnects through active, latest, or by-ID lookup and requests bounded cancellation separately. One content-free, revisioned Resume Run Snapshot reports the fixed candidate set, lifecycle, immutable stopping decision, progress, committed spend, and atomically sealed completion references; its revision may advance after the run finishes for audited late completion or trustworthy spend settlement. Unresolved Resume Artifact Quarantines remain independently discoverable through a worklist, while their stable Artifact Sets expose revision-guarded, asynchronous reconciliation and compensation as distinct actions. Artifact Set identity is also the durable authority for completed PDF download. Private source, generation, checkpoint, provider, and recovery evidence is never part of this public contract.

## Consequences

- Route paths, operation IDs, request and response schemas, idempotency semantics, and typed conflicts become generated-client compatibility commitments that require explicit migration to change.
- The dashboard must treat `202 Accepted` as durable command acceptance, poll stable resource identities, distinguish lifecycle from stopping outcome, and tolerate safety-relevant revisions after a run is finished.
- Safe content-free run snapshots, bounded candidate summaries, Artifact Set snapshots, and idempotency bindings are retained without automatic time-based pruning in V1.
- Operators receive no generic retry, acknowledge, force-complete, or force-delete command; reconciliation and compensation remain separate evidence-gated workflows.
- Exact idempotency binding lookup precedes active-state and revision checks: a replay confirms historical command acceptance and returns the resource's current safe snapshot, while a changed canonical request conflicts.
- Replacing `POST /api/v1/resumes/create` and `GET /api/v1/resumes/{resumeId}/pdf` requires one coordinated API, generated-client, and dashboard cutover that never leaves two supported Resume writers; target `1` is the canonical single-Resume replacement.
- Legacy Resume-ID-only PDFs are not adopted into Artifact Sets and cease to have a supported API download route at that cutover.

The exact public shapes, route family, conflict precedence, retention, and migration contract are specified in [Define the operator-visible Resume Run contract](../../../../../../../.scratch/tickets/durable-batched-resume-creation/08-define-operator-visible-resume-run-contract.md).
