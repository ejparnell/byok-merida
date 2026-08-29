# Prototype the durable Resume Batch dashboard

Parent: [Wayfinder: Durable Batched Resume Creation](map.md)

Type: prototype

Status: ready-for-human

State: closed

Assignee: codex

Blocked by: [Define the operator-visible Resume Run contract](08-define-operator-visible-resume-run-contract.md)

## Question

Given the agreed operator-visible Resume Run contract, what compact dashboard interaction makes the server-selected Resume Batch Target, Match Score threshold and ordering, asynchronous lifecycle, progress and Committed Spend, cancellation limits, partial failures, and completed artifact links understandable while an independent Application Analysis Run may also be active?

The prototype should cover the target control and queue-preview language, immediate queued acceptance, reload reconnection, candidate and artifact presentation, retained terminal results, readiness and polling failures, cancellation warnings, safe next-run behavior, pagination and refresh, and the removal of per-row Create Resume buttons and checkbox selection.

## Answer

Use the **Queue + inspector** structure for the durable Resume Batch dashboard. It keeps the live eligible-queue preview, target control, pagination, refresh, and explicit server-selection language in a persistent left pane while a separate right pane follows the accepted run, fixed Candidate Set, safe current stage, progress, Committed Spend, cancellation drain, and atomically published result links.

The split is the clearest protection against treating visible queue rows as a client-selected batch: the queue remains a preview and next-run control surface, while the inspector is visibly bound to one durable server snapshot. Expandable candidate rows preserve compactness without hiding partial failures or retained outputs, and the layout collapses to queue-then-inspector order on narrow screens. The independent Application Analysis Run notice remains above both panes so concurrency does not look like shared progress or spend.

The throwaway UI prototype is mounted in development inside the existing `/dashboard` Resume Creation section at `apps/web/src/features/dashboard/prototype-resume-run-dashboard/`. Run it with:

```sh
npm run resume-run-dashboard-prototype
```

The in-page prototype-state control covers ready, immediate `202` queued acceptance, running/reconnected, polling failure with a retained snapshot, cancellation drain, spend-limited terminal results with late artifact recovery, and readiness rejection. All interactions are in-memory and make no backend writes. The development-only prototype replaces the old row-level Create Resume presentation, uses no checkboxes, and leaves production rendering unchanged.

The losing Control tower and Candidate ledger variants, their `?variant=` routing, and the floating keyboard switcher have been removed. Production implementation should rewrite this selected structure against the generated Resume Run API rather than promoting the mock prototype directly.
