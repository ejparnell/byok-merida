# Deepen Application-Ready Resume Draft module

Application-Ready Resume Draft owns the path from a Fit Score plus Master Resume evidence to rendered Job-Specific Resume blocks behind one module interface.

## Context

The architecture review found that Resume Creation knew too much about draft assembly: Resume Claim Trace repair, work-experience role completion, bullet-count rules, fixed template rendering, and thin-draft failure modes.

Existing decisions still stand:

- ADR-0020 requires generated claims to come only from supported evidence.
- ADR-0021 requires Resume Claim Traces.
- ADR-0024 requires preserving Master Resume role structure and chronology.
- ADR-0032 requires application-ready drafts with every Master Resume role and 5 to 7 evidence-backed bullets per role.

The problem was the seam, not the draft rules. Resume Creation should sequence Notion reads and writes; it should not own the rules that make a draft application-ready.

## Decision

Create a feature-owned `ApplicationReadyResumeDraft` module in `src/features/resumes/lib/applicationReadyResumeDraft.js`.

Its external interface is:

- `create({ resumeName, jobPosting, masterEvidenceItems, fitScore })`

The module owns Master Resume role skeleton extraction, fixed-template role validation, the injected resume-generation adapter call, Resume Claim Trace repair, role completion from Master Resume evidence, bullet-count enforcement, and Notion block rendering.

Resume Creation now receives rendered Resume and Resume Fit Analysis blocks from the module and keeps Notion sequencing: read source pages, run Resume Fit Analysis, create an unlinked Resume draft, append clean Resume blocks, create the related Resume Fit Analysis Note, then attach the Resume relation.

## Consequences

- Locality improves because application-ready draft rules live together.
- Leverage improves because tests exercise draft behavior through one interface without Notion fakes.
- Resume Creation is thinner and stays focused on workflow sequencing.
- If this module were deleted, claim repair, role completion, template validation, bullet limits, and rendering would reappear in Resume Creation.
