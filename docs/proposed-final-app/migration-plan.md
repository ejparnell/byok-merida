# Migration Plan

This plan migrates the proven Node prototype into the FastAPI and React target one workflow at a time. The prototype remains runnable until each workflow passes parity at its public module interface.

## Current State

Completed:

- versioned prototype parity inventory
- accepted dashboard and extension interaction prototypes
- target workflow module seams and dependency direction
- FastAPI `/api/v1` shell and OpenAPI schema
- workflow-owned Python store interfaces
- persisted demo adapter and deterministic demo workflow results
- production React `/dashboard`
- production React MV3 review-first side panel
- PDF download and demo reset
- public REST and UI-session tests

Not yet cut over:

- real Notion store adapters
- real DeepSeek task-specific model adapters
- Python ports of the full Matching and evidence-validation policies
- real Resume artifact commit and compensation
- parity-based retirement of Node workflow routes

## Cutover Rule

Each workflow is a vertical migration slice. A slice may cut over only when:

1. the real adapter satisfies the workflow-owned interface conformance suite;
2. every relevant `parity_required` and `target_addition` fixture passes;
3. forbidden effects and private-data logging checks pass;
4. idempotency, commit ordering, and cleanup cases pass;
5. the React caller works through the same OpenAPI contract used by demo mode;
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

## Slice 4: Real-Mode Enablement

Enable `MERIDA_MODE=real` only after all three slices pass readiness and parity. Generate the frontend client from the accepted OpenAPI document, add CI gates for backend tests and both React builds, and refresh setup/operations docs.

## Slice 5: Prototype Retirement

Archive or remove Node routes only after the equivalent FastAPI workflow has operated successfully with existing Notion data and a rollback point is recorded. Preserve historical prototype docs and parity fixtures as migration evidence.
