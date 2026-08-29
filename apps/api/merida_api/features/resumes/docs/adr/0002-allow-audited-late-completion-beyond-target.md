# Allow audited late Resume Completion beyond the Resume Batch Target

A Resume Run may backfill past a candidate whose run-owned Resume Artifact Set is under potentially sealable Resume Artifact Quarantine, rather than keeping the whole run active indefinitely. If audited later reconciliation proves that set complete, it seals and counts as truthful run history even when the completion count then exceeds the Resume Batch Target; the run's already-recorded terminal outcome remains unchanged. This deliberately accepts bounded exceptional overshoot so Merida neither discards valid owned work nor lets one isolated quarantine block the batch.

## Consequences

- A candidate with a potentially sealable Resume Artifact Quarantine remains `recovering`, even after its owning run finishes.
- A terminal snapshot may later show more completions than its target, or reach its target while retaining an earlier exhaustion or cancellation outcome.
- Late overshoot is bounded by the fixed Resume Candidate Set; quarantine never adds or reevaluates a candidate.
