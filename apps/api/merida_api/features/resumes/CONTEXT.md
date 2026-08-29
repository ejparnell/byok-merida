# Resumes

The Resumes context owns evidence-gated Resume Creation, from selecting eligible analyzed Applications through committing Job-Specific Resume artifacts. Notion remains the durable record-management surface for completed Resumes and Resume Fit Analysis Notes.

## Language

**Resume Run**:
A durable record of one operator request for batched Resume Creation, including its target, Resume Candidate Set, progress, spend, and terminal outcome. Creating the run does not wait for Resume Creation work to finish.
_Avoid_: HTTP request, batch call

**Resume Run Snapshot**:
The content-free operator projection of a Resume Run's durable identity, monotonic revision, execution and stopping timestamps, progress, spend, complete fixed Resume Candidate Set, artifact references, and stopping decision. A finished snapshot may gain audited completions or later spend settlement without changing its recorded outcome.
_Avoid_: Private checkpoint, immutable terminal response, provider trace

**Active Resume Run**:
The queued, running, or cancelling Resume Run that holds the Resumes context's single scheduling claim. It is independent of any active Analysis Run. Finished runs do not qualify, and an unresolved Resume Artifact Quarantine whose automatic mutation has stopped does not by itself keep its owning run active.
_Avoid_: Latest Resume Run, active quarantine, overlapping Resume Runs

**Latest Resume Run**:
The Resume Run with the greatest immutable creation order, regardless of whether it is active or finished. Later settlement, reconciliation, or audited completion updates do not change which run is latest.
_Avoid_: Active Resume Run, most recently updated run, run history

**Resume Run Outcome**:
The immutable category explaining why a Resume Run stopped scheduling new work: target met, spend limited, Resume Attempt Budget exhausted, queue exhausted, cancelled, authorization blocked, or Run-Scoped failure. It may be decided while safe drain continues before the run finishes; a separate bounded reason code carries the specific safe cause.
_Avoid_: HTTP status, generic success or failure

**Resume Run Lifecycle**:
The execution phase of a Resume Run: queued, running, cancelling, or finished. Candidate recovery, artifact compensation, and quarantine do not create additional run phases.
_Avoid_: Resume Run Outcome, paused run, recovery status

**Resume Batch Target**:
The explicitly selected number of Resume Completions, from one through ten, that the operator asks one Resume Run to pursue rather than an attempt count or queue-page size. Normal execution stops at the target, but audited late completion of an already-owned Resume Artifact Set under Resume Artifact Quarantine may exceptionally exceed it without rewriting the terminal outcome.
_Avoid_: Batch size, selected rows, queue limit

**Resume Completion**:
An immutable historical outcome recorded after one Resume Run verifies its committed Job-Specific Resume, Resume Fit Analysis Note, PDF, and final Resume-to-Application relation. Later workspace mutations do not rewrite run progress; a same-run recovery may count before completion, but an independently existing Resume never does.
_Avoid_: Processed Application, existing Resume

**Resume Completion Summary**:
The content-free result projection atomically published with one Resume Completion: its seal time, stable Resume and Note identities and URLs, and its Artifact-Set-addressed PDF filename and download URL. Every member is required after sealing and the entire summary is absent beforehand.
_Avoid_: Partial result, provider response, Resume Artifact Checkpoint

**Resume PDF Basename**:
The immutable human download name finalized with a Resume Artifact Set from normalized Company, Role, and configured User components. It is safe presentation metadata and never identifies, locates, proves ownership of, or permits adoption of the stored PDF.
_Avoid_: PDF storage key, Resume Artifact Set ID, ownership evidence

**Resume Completion Gate**:
The final ownership-sensitive revalidation surrounding the relation-last commit for one candidate. A Resume Completion counts only after a post-attachment stable observation verifies the admitted source and eligibility plus the run-owned Resume as the sole active Job-Specific Resume relation.
_Avoid_: Artifact creation, independent Resume

**Resume Artifact Set ID**:
An opaque, immutable identity shared by the Job-Specific Resume, Resume Fit Analysis Note, and PDF that one Resume Run candidate owns. It distinguishes same-run artifacts from independently existing or similarly titled artifacts.
_Avoid_: Resume Run ID, Notion page ID, title match, filename match

**Resume Artifact Set Snapshot**:
The content-free operator projection of one Resume Artifact Set's stable owning run, candidate ordinal, Application identity and captured label, safety-relevant revision, disposition, pending boundary, quarantine, available actions, and sealed result references. It remains addressable after quarantine clears, recovery continues, or the set becomes terminal; its revision may expose a hidden safety-relevant evidence change even when the other coarse fields render identically.
_Avoid_: Resume Run Snapshot, Resume Artifact Checkpoint, artifact document

**Resume Artifact Set Disposition**:
The forward-or-terminal condition of one Resume Artifact Set: recoverable, compensation required, sealed, or compensated. It is independent of Resume Candidate State and any nullable Resume Artifact Quarantine, which remains a separate mutation lock rather than a disposition.
_Avoid_: Resume Candidate State, Resume Artifact Quarantine, artifact effect

**Resume Artifact Pending Boundary**:
The earliest canonical forward or compensation boundary of one Resume Artifact Set that has not yet been freshly verified and durably recorded. It remains at the same value through intent and dispatch, advances only from exact observation, and is absent after sealing or verified compensation; final relation attachment remains pending until the Completion seal also commits.
_Avoid_: Latest requested effect, latest dispatched effect, stale journal phase

**Artifact Document Digest**:
The versioned fingerprint of a Resume or Note's canonical ordered block kinds, nesting depths, and normalized text. It proves semantic artifact identity independently of equivalent Notion Markdown formatting or PDF byte encoding.
_Avoid_: Raw Markdown hash, PDF checksum, approximate content match

**Artifact Request Digest**:
The SHA-256 fingerprint of the exact enhanced-Markdown request bytes prepared for one Notion artifact create. It proves wire-request identity but does not replace the semantic Artifact Document Digest.
_Avoid_: Artifact Document Digest, returned Markdown hash

**PDF Byte Digest**:
The SHA-256 fingerprint of one exact rendered PDF byte sequence. The recovery record binds it to the Resume's Artifact Document Digest and Resume Artifact Set ID.
_Avoid_: Artifact Document Digest, filename identity

**Same-Run Artifact Recovery**:
The forward completion of a verified partial Resume Artifact Set by its owning Resume Run before a Resume Completion has been recorded, preserving valid owned artifacts and accepted provider output. It never adopts independent artifacts or restarts the candidate as a fresh artifact attempt.
_Avoid_: Historical repair, cleanup-and-regenerate, artifact adoption

**Resume Artifact Quarantine**:
A durable mutation lock for an Application whose Resume Artifact Set has unprovable checkpoint availability, ownership, content, relation state, result reconstruction, or cleanup. Its operator projection identifies the bounded reason, the current episode's entry time, and the latest evidence-backed assessment time without exposing the evidence itself. It is independent of candidate and run outcomes, does not expire, and permits only an audited return to recovery, proof of completion, or strict compensation before any later Resume attempt.
_Avoid_: Terminal failure, warning, timed retry, acknowledgement-only unblock

**Resume Artifact Quarantine Worklist**:
The operator-visible collection of unresolved Resume Artifact Quarantines, independent of Resume Run lifecycle and presentation history. It remains discoverable after an owning run releases its active claim and while later unrelated Resume Runs execute.
_Avoid_: Active Resume Run, run history, retry queue

**Audited Resume Artifact Reconciliation**:
A durable operator request to re-observe one quarantined Resume Artifact Set that may return the same set to forward recovery or seal a proven completion. It never deletes or compensates artifacts and cannot substitute acknowledgement for evidence.
_Avoid_: Retry, acknowledgement, force complete

**Resume Artifact Compensation**:
The durable, separately authorized, strict verified reversal of exact run-owned effects for a quarantined Resume Artifact Set that cannot complete safely. It never mutates independent artifacts or a sealed Resume Completion.
_Avoid_: Reconciliation, rollback, force delete

**Resume Artifact Action**:
An operator action currently safe to request for one quarantined Resume Artifact Set: Audited Resume Artifact Reconciliation or, when explicitly permitted, Resume Artifact Compensation. Its availability does not promise that the Application will qualify for a future Resume Run.
_Avoid_: Retry, generic resolution, acknowledgement

**Active Resume Artifact Action**:
The single durable reconciliation or compensation intent currently being processed for one Resume Artifact Set. Its presence, kind, acceptance time, and current quarantine episode survive restart and forward recovery until the action reaches a sealed, compensated, or safely re-quarantined idle boundary; it suppresses competing actions and exposes no worker, lease, or percentage detail.
_Avoid_: Resolution job, Resume Run state, provider attempt

**Resume Artifact Checkpoint**:
A recovery-scoped private copy of one Resume Artifact Set's validated Resume and Note documents, retained while Same-Run Artifact Recovery or verified compensation remains possible. It may outlive the owning run while the Artifact Set is under Resume Artifact Quarantine; it is not source evidence, provider output, or a historical repair archive.
_Avoid_: Run metadata, prompt log, permanent artifact archive

**Historical Artifact Drift**:
The later removal or mutation of an artifact or relation after its Resume Completion was sealed. It does not reopen the original run or authorize a replacement Resume; repair or retirement requires a separate future workflow.
_Avoid_: Same-Run Artifact Recovery, failed completion, new-run retry

**Resume Attempt Budget**:
The maximum number of distinct eligible Applications a Resume Run may evaluate while pursuing its Resume Batch Target. It is twice the target, bounded by the eligible queue, and each Application consumes at most one evaluation when its Resume Candidate Admission commits, even when that admission rejects it.
_Avoid_: Resume Batch Target, retry limit

**Resume Candidate Set**:
The fixed Match Score-descending snapshot of eligible Application identities captured for a Resume Run, containing at most its Resume Attempt Budget. Later queue additions, reorderings, and above-threshold Match Score changes do not change its identities or order.
_Avoid_: Live queue, visible queue page

**Resume Candidate Consideration**:
The durable fact that one fixed Resume Candidate has received its first disposition beyond pending, whether or not Resume Candidate Admission consumed an evaluation. The pre-admission quarantine guard therefore counts a consideration but not an evaluation.
_Avoid_: Resume Candidate Admission, Resume Completion, processed Application

**Resume Candidate Label**:
An immutable, presentation-only `Role at Company` label captured for one fixed Resume Candidate when its run begins. It is not source evidence, ordering evidence, artifact naming input, or ownership proof, and later Application edits do not rewrite it.
_Avoid_: Resume Candidate Source Version, live Application title

**Resume Candidate State**:
The safe lifecycle of one fixed Resume Candidate: pending, evaluating, recovering, compensating, completed, skipped, failed, or cancelled. It is independent of provider-call accounting and Resume Artifact Set disposition, so quarantine and an indeterminate call are not candidate states.
_Avoid_: Provider call state, Resume Artifact Set disposition

**Resume Candidate Stage**:
The latest domain work boundary entered by a Resume Candidate: admission, requirements, draft, artifact recovery, completion gate, or compensation. It is independent of Resume Candidate State, retains the last reached boundary after terminal disposition, and omits provider-attempt and individual artifact-effect detail.
_Avoid_: Resume Candidate State, provider attempt, artifact effect

**Master Resume Version**:
The single immutable Master Resume evidence basis selected for a Resume Run. Every candidate uses that version while exact proof remains available; later edits, replacement, archival, loss of access, or deletion neither revise nor implicitly cancel the run.
_Avoid_: Live Master Resume, per-candidate Master Resume

**Resume Candidate Source Version**:
The immutable Application evidence basis selected when a Resume Run begins evaluating one candidate. Requirements, drafting, naming, and rendering use the same Company, Role, Match Score observation, Job Content, and Application Analysis values throughout that evaluation.
_Avoid_: Live Application source, mixed source revisions

**Resume Source Version Proof**:
Durable evidence that recovered content is exactly the Master Resume Version or admitted Resume Candidate Source Version already selected by a Resume Run. It permits exact replay but never substitution; unavailable proof prevents dependent work.
_Avoid_: Latest source, approximate match

**Stable Resume Source Observation**:
A complete view of relevant source values that remains identical across bounded verification reads. Only a stable observation may establish or revalidate a source version; it does not claim that Notion provides an atomic snapshot.
_Avoid_: Single read, atomic Notion snapshot, torn source

**Resume Candidate Admission**:
The fail-closed revalidation immediately before a Resume Run evaluates one candidate. Admission requires the Application to remain eligible, source-complete, and internally consistent without an existing Job-Specific Resume; rejection consumes the evaluation but performs no provider work and earns no Resume Completion.
_Avoid_: Queue membership, Resume Completion

**Resume Candidate Continuation Check**:
The fail-closed comparison between an admitted candidate's fixed source and the current relevant Application values before every provider authorization and before artifact work. A definite source change or unavailability stops the evaluation without replacing its source version or granting another evaluation, while an ambiguous workspace read proves neither condition.
_Avoid_: Source refresh, candidate retry

**Candidate-Scoped Failure**:
A definitive defect confined to one Resume Run candidate that ends its evaluation but permits bounded backfill after any required same-run recovery or compensation reaches a safe boundary. It never rolls back earlier Resume Completions, and a coexisting Resume Artifact Quarantine does not change its scope.
_Avoid_: Run-Scoped Failure, Resume Artifact Quarantine

**Run-Scoped Failure**:
A shared provider, workspace, rendering, storage, protected-state, or execution defect for which later candidate work would be unsafe or predictably repeat the same failure. It stops the Resume Run without rolling back earlier Resume Completions and may coexist with an Application-scoped Resume Artifact Quarantine; shared provider or spend authorization loss is the separate authorization-blocked Resume Run Outcome.
_Avoid_: Candidate-Scoped Failure, Resume Artifact Quarantine

**Resume Run Spend Ceiling**:
The hard maximum provider cost Merida may authorize for one Resume Run under approved prices across Fit Requirement extraction, Resume Draft generation, and every recovery or indeterminate call. It is fixed at $1.00 USD regardless of target and does not claim to cap an incorrect external invoice.
_Avoid_: Per-Resume estimate, actual spend

**Spend-Limited Resume Run**:
A Resume Run that preserves its Resume Completions but stops short of its target because the next complete Resume Call Reservation cannot fit under the Resume Run Spend Ceiling. It is a valid partial outcome and never silently changes the Resume Generation Envelope.
_Avoid_: Failed Resume Run, cheaper fallback

**Resume Generation Envelope**:
The approved provider-generation boundary: Fit Requirement extraction uses DeepSeek V4 Flash with high-effort thinking and an 8,000-token reasoning-inclusive output ceiling; Resume Draft generation uses DeepSeek V4 Pro with high-effort thinking and a 16,000-token reasoning-inclusive output ceiling. Each stage has two durable dispatch attempts, giving one candidate four attempts total. Calls are non-streaming JSON requests with fixed deadlines and no model fallback; every recovery consumes the same budget and never silently lowers quality.
_Avoid_: Analysis Generation Envelope, provider defaults, hidden fallback

**Resume Call Reservation**:
The complete worst-case USD-micro amount held before one Resume provider dispatch. It is derived from the exact rendered request at the approved cache-miss input price plus the stage's full reasoning-inclusive output allowance; it never expires, and only proven non-transmission or trustworthy matching usage evidence may release any portion.
_Avoid_: Cost estimate, expected cost, refundable hold

**Resume Input Cost Bound**:
The conservative input quantity used for Resume Cost Authorization: the greater of the exact rendered request's pinned-tokenizer count and complete UTF-8 byte count, plus reviewed stage protocol overhead. It is never inferred from characters, fixtures, or expected cache behavior.
_Avoid_: Prompt estimate, actual input usage

**Resume Cost Authorization**:
The call-by-call approval required immediately before a Resume provider dispatch, granted only after the exact next request's complete Resume Call Reservation is durably held within the Resume Run Spend Ceiling. It never reserves a whole candidate from a projected request.
_Avoid_: Candidate admission, post-call accounting

**Resume Cost Settlement**:
The conversion of a Resume Call Reservation into trustworthy verified provider cost. Unused value is released only after proven pre-transmission failure or matching, reconcilable usage evidence; response usability and billing evidence are judged independently.
_Avoid_: Estimated usage, output validation

**Indeterminate Resume Call**:
A Resume provider call that may have been sent but has no trustworthy matching usage evidence. Its complete reservation remains committed, and any recovery requires a new call slot and Resume Cost Authorization.
_Avoid_: Free retry, failed-before-send call

**Resume Spend Readiness**:
The fail-closed condition that both stages of the Resume Generation Envelope have current cost approval, verified request accounting and evidence capture, accepted provider behavior, and available durable reservation authority. It is required before a Resume Run starts and rechecked wherever stale or unavailable authority could permit another call.
_Avoid_: Requirements-only readiness, configured model

**Resume Run Readiness**:
The complete fail-closed authority required to create a Resume Run, including stable Master Resume selection, Resume Spend Readiness, durable protected state, and workspace and artifact capabilities. Failure rejects the start before a Resume Run or idempotency binding exists.
_Avoid_: Resume Run Outcome, authorization-blocked run

**Resume Run Readiness Reason**:
The bounded capability-level explanation for a rejected Resume Run start, selected before any run or idempotency binding exists. It identifies the first failed configuration, durable-state, workspace, Master Resume, artifact, envelope, provider-approval, or acceptance-probe gate without exposing raw integration or private evidence.
_Avoid_: Resume Run Outcome, raw readiness error, validation message

**Resume Spend Enforcement Authority**:
The Merida backend boundary that atomically decides whether a complete Resume Call Reservation fits under approved prices before dispatch. Account-wide provider balances and gateway controls are defense in depth; provider adherence to approved prices remains an external billing assumption.
_Avoid_: Provider balance, post-call usage monitor

**Resume Committed Spend**:
The portion of a Resume Run's authorization ceiling occupied under approved prices by verified provider cost, active reservations, and complete reservations retained for Indeterminate Resume Calls. It is the primary operator-facing value, may exceed the eventual bill, and is not a guarantee against provider pricing misconduct.
_Avoid_: Actual cost, estimated spend

**Resume Spend Snapshot**:
The exact run-level operator view of the Resume Run Spend Ceiling, verified cost, active and indeterminate reservations, Resume Committed Spend, and remaining authorized budget. It never apportions money to candidates or presents committed exposure as an invoice.
_Avoid_: Candidate cost, actual bill, dollar-formatted authority

**Cancelled Resume Run**:
A Resume Run whose operator cancellation prevents every later candidate admission and provider call without rolling back prior Resume Completions. Repeated cancellation does not rewrite the first stopping decision; a valid in-flight Draft or already-started Resume Artifact Set may still reach Resume Completion through Same-Run Artifact Recovery, while Requirements alone never authorize another call.
_Avoid_: Rolled-back run, refunded run

**Resume Match Threshold**:
The minimum persisted Application Match Score required for Resume Creation eligibility. An Application qualifies at 70 percent or higher; Resume Creation validates but does not recompute or overwrite that Applications-owned score.
_Avoid_: Soft preference, display filter

**Resume Fit Score**:
The Resumes-owned assessment of how strongly the selected Master Resume Version supports one candidate's Fit Requirements. It may block Resume Creation but never replaces or rewrites the Application's Match Score.
_Avoid_: Match Score, Resume Match Threshold

**Resume Creation Queue**:
The ordered set of Applications currently eligible for Job-Specific Resume creation after applying the Resume Match Threshold and excluding any Application under active Resume Artifact Quarantine. Applications with higher Match Scores come first.
_Avoid_: Visible page, selected Applications, retry-eligible flag
