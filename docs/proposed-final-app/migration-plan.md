# Migration Plan

This plan migrates the proven Node prototype into the FastAPI and React target one workflow at a time. The prototype remains runnable until each workflow passes parity at its public module interface.

## Current State

Completed:

- versioned prototype parity inventory
- accepted dashboard and extension interaction prototypes
- target workflow module seams and dependency direction
- FastAPI `/api/v1` shell and OpenAPI schema
- workflow-owned Python store interfaces
- deterministic test fakes behind workflow-owned interfaces
- production React `/dashboard`
- production React MV3 review-first side panel
- PDF download through the shared artifact contract
- public REST and UI-session tests
- task-specific DeepSeek Application Analysis structured-output adapter
- evidence-validated Application Analysis drafts with one bounded repair attempt
- deterministic `matching-v1` Match Score calculation against Master Resume evidence
- one LangGraph invocation per Application Analysis item
- task-specific DeepSeek Resume Fit Requirement and Resume Document generation
- deterministic Resume Matching and pre-write evidence gates
- role-owned claim traces, chronology preservation, and five-to-seven bullet policy
- one canonical Resume Document for Notion and PDF
- real Resume artifact commit, relation-last completion, reverse compensation, and durable recovery journal
- workflow-scoped readiness, structured Capture metadata, and independently resilient dashboard sections
- fixture-owned target regressions that exercise every required frozen fixture ID through a final-app workflow or public seam

Not yet cut over:

- real-environment conformance and smoke acceptance for each Notion store
- default operator-command switch and observation window
- parity-based retirement of Node workflow routes

All three workflows now have their real repository-side implementations, but they remain behind the operational cutover gate until the target fixture manifest and bounded real-environment smoke run pass.

## Cutover Rule

Each workflow is a vertical migration slice. A slice may cut over only when:

1. the real adapter satisfies the workflow-owned interface conformance suite;
2. every relevant `parity_required` and `target_addition` fixture passes;
3. forbidden effects and private-data logging checks pass;
4. idempotency, commit ordering, and cleanup cases pass;
5. the React caller works through the accepted OpenAPI contract exercised by credential-free ASGI tests;
6. the prototype route remains available as a fallback until the slice is accepted.

## Slice 1: Real Application Capture

Implement `CaptureStore` with the Notion compatibility mapping for the unchanged Applications database. Preserve canonical URL duplicate detection, readable Capture Summary and Job Content blocks, schema validation, and `To Apply` defaults.

Exit: the React side panel can prepare and confirm against Notion, duplicate confirmation is idempotent, and no private Job Content enters extension persistence or normal logs.

## Slice 2: Real Application Analysis

Implement `ApplicationAnalysisStore`, the task-specific DeepSeek Analysis model adapter, evidence validation, deterministic Matching, body-first commit, and property repair.

Exit: bounded sequential batches preserve per-Application isolation, unsupported signals are rejected, exact Match Score recovery works, and the React dashboard receives one final result.

## Slice 3: Real Resume Creation

Port Fit Requirement extraction, Matching, evidence gating, Resume Draft generation, claim traces, Notes rendering, PDF rendering, and `ResumeArtifactCommitter` behind `ResumeCreationStore`.

Exit: one-at-a-time creation is idempotent, Resume and PDF render from the same validated document, final attachment is last, and every partial failure compensates in reverse order with explicit residue.

## Slice 4: Real Runtime Completion

Complete the single real composition only after all three slices pass readiness and parity. Generate the frontend client from the accepted OpenAPI document, add CI gates for backend tests and both React builds, and refresh setup/operations docs. There is no mode selector or fictional fallback.

## Slice 5: Prototype Retirement

Archive or remove Node routes only after the equivalent FastAPI workflow has operated successfully with existing Notion data and a rollback point is recorded. Preserve historical prototype docs and parity fixtures as migration evidence.
