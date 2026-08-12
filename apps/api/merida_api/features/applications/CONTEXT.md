# Applications

The Applications context owns a pursuit from reviewed capture through evidence-backed Application Analysis. It selects eligible Applications for bounded operator-initiated analysis work while Notion remains the durable record-management surface.

## Language

**Analysis Run**:
A durable record of one operator request for Application Analysis, including its target, budgets, progress, and terminal outcome. Creating the run does not wait for its analysis work to finish.
_Avoid_: HTTP request, batch call

**Analysis Run Outcome**:
The reason a finished Analysis Run stopped: target met, spend limited, Attempt Budget exhausted, queue exhausted, cancelled, authorization blocked, or unrecoverably failed. Per-Application failures do not by themselves make the run failed.
_Avoid_: HTTP status, generic success or failure

**Analysis Batch Target**:
The number of successful Application Analysis completions requested by the operator from one run. Failed or skipped attempts do not satisfy the target.
_Avoid_: Batch limit, batch number

**Analysis Completion**:
An outcome in which an Application leaves the Analysis Queue with a readable analysis body and finalized analysis properties. Both a newly produced analysis and the repair of an existing analysis are completions.
_Avoid_: Analysis success, processed Application

**Analysis Signal Set**:
The prioritized, evidence-backed set of three to ten concrete Skill Signals used for Application Match Score and presentation. Required signals precede preferred and other useful signals, near-duplicates are merged, and the set is intentionally not an exhaustive copy of Job Content.
_Avoid_: Complete requirements list, unbounded Skill Signals

**Analysis Generation Envelope**:
The provider-generation boundary for an Application Analysis call: thinking is explicitly enabled at high effort with at most 8,000 generated tokens shared by reasoning and final JSON. Recovery never disables thinking or silently lowers analysis quality.
_Avoid_: Non-thinking fallback, provider defaults

**Attempt Budget**:
The maximum number of distinct eligible Applications an analysis run may attempt while pursuing its Analysis Batch Target. It is twice the target, bounded by the available queue, and an Application may consume at most one attempt per run.
_Avoid_: Retry limit, spend budget

**Run Candidate Set**:
The fixed, canonically ordered snapshot of eligible Application IDs captured for an Analysis Run, containing at most its Attempt Budget. Candidates are revalidated just before use, but later queue additions and reordering do not change the set.
_Avoid_: Live queue, visible dashboard page

**Application Call Budget**:
The maximum number of provider calls available to one Application attempt, shared by its initial analysis, transport retries, and structured-output repairs. An attempt has three calls total, and each call still requires Cost Authorization.
_Avoid_: Attempt Budget, separate retry counters

**Analysis Spend Ceiling**:
The maximum provider cost permitted for one operator-initiated Analysis Run, including every initial call, repair, retry, and failed call. The ceiling is fixed at $0.50 USD regardless of the Analysis Batch Target.
_Avoid_: Attempt Budget, estimated cost

**Spend-Limited Run**:
An Analysis Run that preserves its Analysis Completions but stops short of its target because another provider call could exceed the Analysis Spend Ceiling. It is a valid partial outcome, not a rollback or total failure.
_Avoid_: Failed batch, over-budget run

**Cancelled Run**:
An Analysis Run for which the operator stopped future provider calls. A call already in flight may still produce and commit an Analysis Completion, and all earlier completions remain committed.
_Avoid_: Rolled-back run, aborted provider charge

**Cost Authorization**:
The approval required immediately before an analysis provider call, granted only when that call's worst-case charge fits within the run's remaining Analysis Spend Ceiling. A call with unknown or unverifiable cost is not authorized.
_Avoid_: Cost estimate, post-call accounting

**Input Cost Bound**:
The conservative input-token quantity used for Cost Authorization, calculated from the exact rendered request using both the approved model tokenizer and a complete UTF-8 byte upper bound with verified protocol overhead. It is never a characters-to-tokens estimate.
_Avoid_: Actual usage, prompt-size guess

**Cost Settlement**:
The conversion of a provider call's worst-case reservation into trusted actual cost. Unused budget is released only for a proven pre-transmission failure or a valid settlement receipt; otherwise the full reservation remains consumed.
_Avoid_: Estimated usage, optimistic refund

**Committed Spend**:
The conservative portion of an Analysis Run's ceiling already occupied by verified provider cost, active reservations, and indeterminate reservations treated as consumed. It is the primary operator-facing spend value and may exceed verified actual cost.
_Avoid_: Actual cost, optimistic remaining balance

**Approved Analysis Model**:
An exact provider endpoint and model combination whose input price, reasoning-inclusive output price, and output bound are trusted for Cost Authorization. Approval expires 30 days after its pricing evidence is verified; a configured model with missing or expired approval cannot be used for Application Analysis.
_Avoid_: Configured model, supported provider

**Spend Enforcement Authority**:
The Merida backend boundary that atomically reserves a provider call's entire worst-case charge before dispatch and admits it only when that reservation fits within the Analysis Run's remaining ceiling. Provider and gateway limits are defense in depth because post-call blocking alone does not enforce the run ceiling.
_Avoid_: Gateway spending limit, usage tracker, post-call accounting

**Indeterminate Attempt**:
An Application attempt whose provider call may have incurred cost but produced no reconcilable outcome. Its reservation is treated as consumed, and any fresh retry requires separate Cost Authorization.
_Avoid_: Free retry, provider failure

**Analysis Commit Quarantine**:
A durable exclusion for an Application whose Notion Analysis mutation has an unknown remote result. It remains outside later queue snapshots until Merida observes the committed Analysis or an operator resolves it from affirmative non-dispatch or definitive-rejection evidence; absence and elapsed time are not proof.
_Avoid_: Timed retry, assumed rollback

**Candidate-Scoped Failure**:
A defect specific to one Application, such as unusable source content or repeatedly invalid model output, that permits the Analysis Run to continue to its next candidate.
_Avoid_: Provider outage, run failure

**Run-Scoped Failure**:
A shared provider, authorization, workspace, or storage defect for which trying later candidates would be unsafe or predictably repeat the same failure. It stops the Analysis Run without rolling back earlier completions.
_Avoid_: Candidate failure, failed Application
