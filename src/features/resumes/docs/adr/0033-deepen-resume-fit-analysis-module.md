# Deepen Resume Fit Analysis module

Resume Fit Analysis owns the full path from Fit Requirements to Fit Score behind one module interface.

## Context

The architecture review found that Resume Creation knew too much of the Resume Fit Analysis protocol: Fit Requirement extraction, Job Content support validation, candidate generation, runtime scoring, `generationAllowed`, and insufficient-evidence summaries.

Existing decisions still stand:

- ADR-0015 requires explicit ML/NLP analysis for Resume Fit Analysis.
- ADR-0017 splits the runtime between Node orchestration and repo-local Python ML/NLP primitives.
- ADR-0030 uses two-stage Fit Requirement matching.

The problem was the seam, not those decisions. The Python runtime is a real adapter, but Resume Creation should not need to know the candidate-then-score protocol.

## Decision

Create a feature-owned `ResumeFitAnalysis` module in `src/features/resumes/lib/resumeFitAnalysis.js`.

Its external interface is:

- `health()`
- `analyze({ jobContent, jobPostingAnalysis, masterEvidenceItems })`

The module owns Fit Requirement extraction, support validation against Job Content, candidate matching through the Python runtime adapter, Fit Score calculation, and insufficient-evidence failure details. Resume Creation receives one analysis result and uses the returned Fit Score for evidence-grounded resume generation.

The Local Operator and Resumes route adapter may inject a `resumeFitAnalysis` adapter directly. Lower-level `fitRuntimeClient` and `resumeLlm` injection remains as compatibility glue for existing tests and server construction, but the Resume Creation caller depends on the deeper module interface.

## Consequences

- Locality improves because Fit Score rules and failure summaries live with Resume Fit Analysis.
- Leverage improves because callers and tests can exercise the fit workflow through one interface.
- The Python runtime remains hidden behind the Resume Fit Analysis module.
- If this module were deleted, extraction, validation, candidate matching, scoring, and insufficient-evidence behavior would reappear in Resume Creation.
