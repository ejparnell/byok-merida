# Tickets: Durable Batched Resume Creation

Status: ready-for-agent

State: open

Source: [Wayfinder: Durable Batched Resume Creation](map.md)

Implement durable asynchronous batched Resume Creation from approved provider and spend authority through fixed-source evaluation, recoverable Artifact Sets, explicit failure and cancellation semantics, the operator-visible contract, and one coordinated dashboard cutover.

Work the **frontier**: any ticket whose blockers are all complete can start. [Extract the shared conservative Provider Spend kernel](#1-extract-the-shared-conservative-provider-spend-kernel), [Produce one exact bounded two-stage Resume](#2-produce-one-exact-bounded-two-stage-resume), [Read complete Stable Resume Source Observations](#8-read-complete-stable-resume-source-observations), and [Prefactor dashboard durable-resource observation plumbing](#29-prefactor-dashboard-durable-resource-observation-plumbing) form the current parallel frontier. Later tickets follow only the blocking edges that genuinely gate their behavior.

## 1. Extract the shared conservative Provider Spend kernel

**What to build:** Create one context-neutral provider-spend policy kernel that preserves every existing Application Analysis authorization and settlement behavior while making the proven cost machinery reusable by Resume Creation without importing Applications-owned language or policy.

**Blocked by:** None — can start immediately.

- [ ] The shared kernel represents reviewed exact endpoint-and-model approvals, pricing evidence and validity, tokenizer and protocol provenance, approval and request fingerprints, conservative cost estimates, usage receipts, and settlement results without Analysis-specific names.
- [ ] The Input Cost Bound remains the greater of the pinned-tokenizer count and complete rendered UTF-8 byte count, plus reviewed protocol overhead.
- [ ] Context admission, cache-miss authorization, reasoning-inclusive output pricing, integer USD-micro arithmetic, and upward rounding preserve their current behavior exactly.
- [ ] Settlement releases value only from a trustworthy matching receipt and keeps missing, malformed, mismatched, contradictory, or out-of-bound evidence conservative.
- [ ] Approval validation remains fail-closed for missing, stale, duplicated, malformed, unknown, or mismatched entries and unavailable tokenizer evidence.
- [ ] The kernel supports distinct output allowances, protocol bounds, and prices per approved model rather than retaining the Analysis-only 8,000-token assumptions.
- [ ] Applications continues to own its Flash approval, $0.50 Analysis Spend Ceiling, Analysis ledger, outcome language, and public contract.
- [ ] Resumes can depend on the shared kernel without depending on Applications-owned modules or persistence types.
- [ ] Existing Application Analysis public behavior, rate-card validation, authorization, settlement, restart, and spend tests remain unchanged and green after migration.
- [ ] Focused parity tests prove that representative Analysis estimates and settlements are identical before and after the prefactor.

## 2. Produce one exact bounded two-stage Resume

**What to build:** Make the existing public Resume Creation flow produce one healthy Job-Specific Resume through the approved two-stage Resume Generation Envelope, with every actual provider transmission explicit, bounded, and evidenced.

**Blocked by:** None — can start immediately.

- [ ] Fit Requirement extraction uses only DeepSeek V4 Flash with thinking explicitly enabled at high effort and an 8,000-token reasoning-inclusive output allowance.
- [ ] Resume Draft generation uses only DeepSeek V4 Pro with thinking explicitly enabled at high effort and a 16,000-token reasoning-inclusive output allowance.
- [ ] Both stages use non-streaming JSON-object requests, 10-second connect and pool timeouts, 120-second write and read-inactivity timeouts, and a 300-second absolute deadline.
- [ ] Each stage has exactly two durable dispatch attempts across initial generation, transient recovery, truncation or empty-output recovery, malformed JSON recovery, and semantic repair; a candidate can never cause a fifth transmission.
- [ ] The transport has no nested automatic retry, never restores a consumed slot, and never changes model, disables thinking, lowers effort, or raises an output allowance during recovery.
- [ ] The current Flash-primary-to-Pro Draft fallback is removed; Pro authors every initial and recovery Draft call.
- [ ] Each call is rendered once into canonical request bytes and the prepared transport sends those exact bytes once.
- [ ] Safe evidence distinguishes proven non-transmission from sent or indeterminate outcomes and captures completion identity, returned model, finish reason, prompt and completion usage, cache usage, total usage, and reasoning-token count.
- [ ] Prompts, Job Content, Master Resume evidence, generated Resume content, and model reasoning remain absent from recorded evidence and logs.
- [ ] Only a `stop` response that passes JSON and semantic validation completes a stage; every other transmitted outcome consumes its stage slot.
- [ ] A healthy request through the existing public Resume Creation acceptance seam still commits its Job-Specific Resume, Resume Fit Analysis Note, PDF, and relation.
- [ ] Deterministic public-flow and prepared-provider tests prove exact bytes, both model envelopes, mixed recovery paths, safe evidence, deadline classification, no fallback, and the four-transmission maximum without making paid provider calls.

## 3. Approve and calculate both Resume stage reservations

**What to build:** Give both exact Resume stages reviewed, reproducible cost authority so Merida can calculate and conservatively settle a complete Resume Call Reservation from the exact prepared request.

**Blocked by:** [Extract the shared conservative Provider Spend kernel](#1-extract-the-shared-conservative-provider-spend-kernel) and [Produce one exact bounded two-stage Resume](#2-produce-one-exact-bounded-two-stage-resume).

- [ ] Resumes owns separate approvals for Flash/8K Requirements and Pro/16K Draft at the exact approved endpoint.
- [ ] Each entry records authoritative cache-hit, cache-miss, and reasoning-inclusive output prices; context and output bounds; source evidence; verification date; a validity window no longer than 30 days; tokenizer provenance; protocol evidence; and a distinct approval fingerprint.
- [ ] Both stage entries use pinned, checksum-verified tokenizer artifacts and independently reviewed protocol overhead for their largest permitted three-message request.
- [ ] Missing, provisional, expired, duplicated, malformed, unknown, or mismatched approval evidence blocks calculation rather than substituting a default.
- [ ] A Requirements reservation prices its exact Resume Input Cost Bound at the approved cache-miss rate plus the complete 8,000-token output allowance.
- [ ] A Draft reservation prices its exact Resume Input Cost Bound at the approved cache-miss rate plus the complete 16,000-token output allowance.
- [ ] The input and output components round upward independently in integer USD micros, and assumed cache hits never reduce authorization.
- [ ] A call whose Resume Input Cost Bound plus output allowance exceeds the approved one-million-token context is rejected without transmission or source truncation.
- [ ] A trustworthy matching receipt may settle a reservation downward using verified cache-hit, cache-miss, and reasoning-inclusive completion usage even when the generated output is unusable.
- [ ] A receipt with missing identity, returned-model mismatch, malformed totals, contradictory cache accounting, or usage beyond the reservation cannot release value.
- [ ] Pure policy tests cover both tokenizer and UTF-8 branches, non-ASCII input, context boundaries, upward rounding, current and expired approvals, both stage prices, and every settlement evidence class.
- [ ] A deterministic calibration test reproduces the documented two-role fixture reservations and labels them as fixture evidence rather than expected production cost or runtime authorization authority.

## 4. Prefactor the transactional $1.00 Resume spend ledger

**What to build:** Establish the Resumes-owned, metadata-only transaction boundary that captures one run's fixed spend policy and can atomically reserve, settle, and project provider exposure without moving private Resume content out of its authoritative systems.

**Blocked by:** [Extract the shared conservative Provider Spend kernel](#1-extract-the-shared-conservative-provider-spend-kernel) and [Prototype the minimal Resume Run durability boundary](06-prototype-resume-run-durability-boundary.md).

- [ ] Every Resume Run durably captures a versioned Resume Run Spend Ceiling of exactly 1,000,000 USD micros, independent of target and without a per-run override.
- [ ] The selected durability design represents safe stage and call identity, approval and request fingerprints, authorization evidence, dispatch state, verified cost, active reservations, and indeterminate reservations.
- [ ] Resume Committed Spend is exactly verified provider cost plus active reservations plus indeterminate reservations, and remaining authorized budget is derived from the captured ceiling.
- [ ] Reservation admission and the corresponding durable call record occur in one serialized transaction before provider dispatch can begin.
- [ ] A reservation equal to the remaining authorized budget is admitted, a reservation one micro greater is denied, and concurrent admissions cannot oversubscribe the captured ceiling.
- [ ] An unavailable, non-transactional, or inconsistent spend ledger fails closed for operations that could authorize provider work.
- [ ] A durable transition marks the final local boundary before dispatch so proven pre-dispatch work can be distinguished from work that may have been sent.
- [ ] Only proven non-transmission can release a complete active reservation; dispatching, sent, or otherwise ambiguous work can retain the full value indefinitely as indeterminate.
- [ ] Each reservation retains the exact approval fingerprint and rates used at authorization without being rewritten by later rate-card changes.
- [ ] Resume and Analysis ledgers remain independent so one overlapping Analysis Run cannot consume, release, or obscure the Resume Run ceiling.
- [ ] Durable records and projected snapshots contain no prompts, Job Content, Master Resume content, generated artifacts, provider payloads, or model reasoning.
- [ ] A focused transactional persistence test proves exact-boundary admission, one-micro denial, concurrent no-oversubscription, non-expiring uncertainty, restart persistence, and the private-content denylist.

## 5. Authorize and settle one Resume candidate under $1.00

**What to build:** Make one candidate traverse Requirements and Draft under the approved public Resume Run seam, reserving immediately before each exact transmission and preserving honest partial progress when the next call cannot fit.

**Blocked by:** [Approve and calculate both Resume stage reservations](#3-approve-and-calculate-both-resume-stage-reservations), [Prefactor the transactional $1.00 Resume spend ledger](#4-prefactor-the-transactional-100-resume-spend-ledger), and [Define the operator-visible Resume Run contract](08-define-operator-visible-resume-run-contract.md).

- [ ] The approved Resume Run creation path captures the fixed 1,000,000-micro ceiling and exposes no target multiplier, request override, or environment override for it.
- [ ] Immediately before every Requirements or Draft transmission, Merida checks current approval, renders the exact request once, calculates the complete Resume Call Reservation, and atomically reserves it.
- [ ] The prepared transport receives exactly the bytes whose fingerprint and cost evidence were reserved; a failed reservation causes zero provider transmissions.
- [ ] Requirements and Draft are authorized independently because the exact Draft request does not exist before Requirements and evidence selection complete.
- [ ] A healthy candidate can settle both stages from trustworthy usage and continue to one Resume Completion without exceeding the ceiling.
- [ ] A valid receipt settles provider cost even when output validation requires the remaining recovery slot; the recovery receives its own fresh authorization.
- [ ] Proven pre-transmission failure releases the reservation but still consumes the stage's durable dispatch-attempt slot.
- [ ] A sent or possibly sent call with untrustworthy evidence becomes an Indeterminate Resume Call whose complete reservation remains committed; recovery requires another slot and reservation.
- [ ] When Requirements spend is committed but the exact Draft reservation cannot fit, no Draft call is sent and the run follows the approved Spend-Limited Resume Run contract without rolling back prior Resume Completions.
- [ ] Spend pressure never changes model, reasoning mode, effort, output allowance, timeouts, or the two-attempt stage budgets.
- [ ] Current pricing and spend-authority readiness are checked before run creation and again immediately before each call; stale or unavailable authority stops new transmissions.
- [ ] Provider-pricing or usage evidence that contradicts approved bounds retains the authorized reservation, stops further transmission, and uses the safe anomaly behavior selected by the Resume Run failure contract.
- [ ] Public acceptance tests use the normal application composition, real transactional Resume ledger, and deterministic rate card, tokenizer, clock, provider, and barriers to cover healthy completion, exact-boundary admission, one-micro denial, denial before any call, and spend limitation after paid Requirements work.

## 6. Recover Resume spend without manufacturing budget

**What to build:** Recover or cancel an unfinished paid Resume Run without duplicating a provider transmission, refunding uncertain work, restoring consumed call slots, or rewriting earlier authorization evidence.

**Blocked by:** [Authorize and settle one Resume candidate under $1.00](#5-authorize-and-settle-one-resume-candidate-under-100).

- [ ] A fresh application instance over the same durable state observes the same captured ceiling, approval evidence, call states, and Resume Committed Spend.
- [ ] A crash before reservation leaves no committed spend, and a reservation durably proven not to have begun dispatch releases completely without restoring its consumed stage slot.
- [ ] A crash, timeout, cancellation, expired lease, or missing response after dispatch may have begun never releases a reservation merely because time passed.
- [ ] A dispatching or sent call with no trustworthy matching receipt becomes or remains an Indeterminate Resume Call with its full reservation committed.
- [ ] A durably recorded matching receipt settles without retransmission even when the process stopped before output validation or candidate progression.
- [ ] Every post-restart recovery transmission consumes an available stage slot and receives a new Resume Cost Authorization under the current approved rate card and remaining ceiling.
- [ ] Earlier reservations retain their original approval fingerprints and rates while later calls use current approval; recovery never recalculates old reservations optimistically.
- [ ] Cancellation prevents new provider calls while allowing trustworthy in-flight usage to settle and ambiguous in-flight work to remain indeterminate.
- [ ] Recovery and cancellation preserve all earlier Resume Completions and never imply that an external provider charge was refunded.
- [ ] A recovered run that no longer passes pricing, model, probe, or transactional-authority readiness sends no additional call and follows the approved safe terminal behavior.
- [ ] Recovery metadata and diagnostics remain content-free and expose neither provider payloads nor private source, generated content, or reasoning.
- [ ] Deterministic fresh-instance tests with controlled transmission barriers cover crashes before reservation, after reservation but before dispatch, during dispatch, after response evidence, after settlement, and during cancellation without sleeps or paid calls.

## 7. Expose exact Resume Committed Spend end to end

**What to build:** Let the operator understand one Resume Run's conservative provider exposure through its approved API and dashboard experience, including sub-cent values that never disappear through presentation rounding.

**Blocked by:** [Authorize and settle one Resume candidate under $1.00](#5-authorize-and-settle-one-resume-candidate-under-100) and [Prototype the durable Resume Batch dashboard](09-prototype-durable-resume-batch-dashboard.md).

- [ ] The approved Resume Run snapshot exposes ceiling, verified provider cost, active reservations, indeterminate reservations, Resume Committed Spend, and remaining authorized budget as integer USD micros.
- [ ] Snapshot values reconcile exactly: committed equals verified plus active plus indeterminate, and remaining equals the captured ceiling minus committed.
- [ ] The public API description and generated client carry the complete typed spend contract without exposing private source, provider payload, generated content, or reasoning.
- [ ] The dashboard's primary spend presentation shows `Committed Spend` against the fixed `$1.00` ceiling.
- [ ] Expanded detail separately shows verified provider cost, active reservations, indeterminate reservations, and remaining authorized budget.
- [ ] Resume Committed Spend is never labeled or described as actual cost or as an unconditional cap on an incorrect provider invoice.
- [ ] One shared formatter renders up to six decimal places, trims trailing zeros, retains at least two decimal digits, and never displays nonzero micros as `$0.00`.
- [ ] Formatting examples include `$0.002405`, `$0.71424`, and `$1.00`, and the existing Analysis spend presentation remains correct after adopting the shared formatter.
- [ ] Active, Spend-Limited, indeterminate, recovered, cancelled, and completed Resume Runs preserve their spend presentation for as long as their approved run result remains observable.
- [ ] API and dashboard tests prove exact reconciliation, labels, formatting, and presentation across verified, active, and indeterminate combinations and after reload recovery.
- [ ] Workflow, frontend, AI-workflow, architecture, operations, and route documentation distinguish the authorization-ledger ceiling from an external provider invoice and document the provider-pricing assumption.
- [ ] The final regression gate proves no local Resume execution, recovery, cancellation, or presentation path raises Resume Committed Spend above 1,000,000 micros.

---

**Source-consistency tranche:** Make every Resume Run and candidate use one coherent, provable source version from run creation through relation-last Resume Completion.

**Source:** [Define Resume Run source consistency and candidate revalidation](04-define-resume-run-source-consistency.md)

Work the **frontier**: [Read complete Stable Resume Source Observations](#8-read-complete-stable-resume-source-observations) starts after the durability prototype selects the observation and proof mechanics. After run creation is source-consistent, Master recovery can proceed alongside candidate admission and generation. Candidate recovery and the pre-attachment gate then form parallel paths into post-attachment verification and sealing.

## 8. Read complete Stable Resume Source Observations

**What to build:** Give Resume workflows one Resumes-owned way to accept a Master Resume or Application only when its identity, relevant properties, complete relations, and selected body content form one coherent observation, while distinguishing definite unavailability from evidence that is merely ambiguous.

**Blocked by:** [Prototype the minimal Resume Run durability boundary](06-prototype-resume-run-durability-boundary.md).

- [ ] A Stable Resume Source Observation represents source identity, every consistency-sensitive property, all relevant relation members, and the complete selected body content needed by Resume Creation.
- [ ] Master Resume observations and Application observations have explicit canonical equality semantics based on the source values the Resumes context owns or consumes.
- [ ] Application observations include Company, Role, current Match Score, status, Analyzed, Job Content, the selected Application Analysis, and the complete active Job-Specific Resume relation.
- [ ] Unrelated Application management fields do not participate in candidate source-version equality.
- [ ] Relevant values must produce the same canonical observation across the bounded verification strategy selected by the durability prototype before the observation is accepted as stable.
- [ ] Relation pagination is complete before an observation can be stable; a related Resume beyond the first response page is never silently omitted.
- [ ] Incomplete pagination, truncated or unsupported selected content, property/body movement, or inconsistent verification reads cannot produce a Stable Resume Source Observation.
- [ ] A definite page-level absence or definitely missing required source is distinguishable from a timeout, rate limit, server error, torn read, or otherwise unverifiable observation.
- [ ] Ambiguous evidence is never converted into evidence of deletion, eligibility, consistency, or permission to continue.
- [ ] Public snapshots, logs, and safe coordination diagnostics expose no Master Resume content, Job Content, Application Analysis, generated content, or other private source material.
- [ ] Deterministic workspace and recorded-Notion conformance tests prove complete pagination, agreeing and moving observations, definite unavailability, ambiguous failures, and stable canonical equality without coupling tests to one exact reread count.
- [ ] Existing synchronous Resume Creation behavior remains green while later tickets adopt the observation seam.

## 9. Start a run from one fixed Master Resume Version and Candidate Set

**What to build:** Make an accepted Resume Run begin from one protected, recoverable Master Resume Version and one immutable, bounded set of eligible Application identities, so every later candidate shares the same evidence basis and the run never starts without its durable privacy and artifact-readiness prerequisites.

**Blocked by:** [Read complete Stable Resume Source Observations](#8-read-complete-stable-resume-source-observations) and [Authorize and settle one Resume candidate under $1.00](#5-authorize-and-settle-one-resume-candidate-under-100).

- [ ] Resume Run creation obtains a Stable Resume Source Observation for the selected Master Resume before the run is accepted.
- [ ] Moving, incomplete, definitely unavailable, or ambiguous Master evidence cannot establish a new Resume Run.
- [ ] The Resumes-owned transaction store includes one production checkpoint vault using AES-256-GCM, a fresh 96-bit nonce per write, an externally supplied versioned 256-bit key, and authenticated associated data binding checkpoint kind and schema to its applicable run, candidate, source-proof, producing-call, and Resume Artifact Set identities.
- [ ] Run creation atomically stores the exact canonical Master Resume Version in a protected Master Source Checkpoint, its safe Resume Source Version Proof, the fixed Resume Candidate Set, spend policy, single-active-run claim, and immutable idempotency binding.
- [ ] Missing, wrong, revoked, transplanted, or tampered checkpoint key or ciphertext evidence fails readiness or recovery closed, and key rotation authenticates with the old key and rewrites a checkpoint atomically while that key remains available.
- [ ] Checkpoint plaintext and keys are absent from ordinary coordination, public state, logs, errors, and raw SQLite, WAL, and SHM inspection; the protected payload admits only the approved checkpoint content and minimal authenticated binding metadata.
- [ ] Resume Run creation also fails before creating durable run state when required `Merida Artifact ID` properties, enhanced-Markdown create and read capability, exact-ID lookup, supported semantic round trips, or digest-verified PDF storage cannot be proved ready.
- [ ] Every candidate in the run is bound to that same Master Resume Version; no per-candidate live Master selection remains.
- [ ] The Resume Creation Queue excludes Applications below the 70 percent Resume Match Threshold before the fixed Candidate Set is selected.
- [ ] The fixed Resume Candidate Set contains the first minimum of the eligible queue size and twice the Resume Batch Target, using the approved run-start ordering and stable tie-breaking.
- [ ] Only Application identities and their fixed order are selected at run creation; each candidate's current source values are deliberately deferred to Candidate Admission.
- [ ] Later queue additions, removals, score changes, eligibility changes, and ordering changes never replace, reorder, or expand the fixed Candidate Set.
- [ ] Later edits, archival, replacement, duplication, unsharing, or deletion of the selected Master page never substitute another version into the accepted run.
- [ ] A later Resume Run may select a newer Master Resume Version without changing the version bound to an earlier run.
- [ ] The approved public run acceptance seam proves stable creation, fixed membership and ordering after workspace mutation, one Master version across multiple candidates, and selection of a newer version by a later run.
- [ ] Public run state and safe durable coordination metadata reveal no Master Resume content or candidate source content.
- [ ] Focused checkpoint-vault and run-creation tests prove authenticated round-trip, identity binding, wrong-key and tamper failure, atomic rotation, plaintext exclusion, readiness rejection, rollback, and one all-or-nothing accepted start.

## 10. Admit one candidate before any spend

**What to build:** Begin one fixed candidate's only evaluation by reloading one complete, stable Application version, applying every eligibility and consistency rule, and durably fixing that version before any provider reservation or artifact effect.

**Blocked by:** [Start a run from one fixed Master Resume Version and Candidate Set](#9-start-a-run-from-one-fixed-master-resume-version-and-candidate-set).

- [ ] Candidate Admission occurs immediately before the candidate's first provider authorization and consumes that identity's one evaluation even when admission rejects it.
- [ ] Admission accepts source values only from a Stable Resume Source Observation and durably binds the resulting Resume Candidate Source Version to the run, candidate identity, and fixed ordinal.
- [ ] The candidate must remain readable, be in To Apply, have Analyzed set to true, and have a current Match Score of at least 70.
- [ ] Company, Role, Job Content, and the selected Application Analysis must all be readable and complete.
- [ ] The complete active Job-Specific Resume relation must be empty; an independently created Resume rejects the candidate and is never adopted or credited as this run's work.
- [ ] A canonical Application Analysis with an embedded Match Score must agree exactly with the current Application Match Score property.
- [ ] A readable legacy Job Posting Analysis with no embedded score may use the Application property as its sole score authority, but that property must still meet the threshold.
- [ ] A score mismatch is rejected without choosing an authority, recomputing the score, or repairing Applications-owned data.
- [ ] An above-threshold score change is accepted into the Candidate Source Version without changing the fixed Candidate Set order; a missing or below-threshold score rejects admission without changing membership.
- [ ] An admitted Candidate Source Version fixes Company, Role, accepted Match Score, Job Content, and Application Analysis before any paid or artifact work.
- [ ] A definite admission rejection creates no reservation, provider transmission, PDF, Resume, Note, relation mutation, or Resume Completion and permits bounded backfill from the next fixed identity.
- [ ] Ambiguous workspace evidence fails closed and cannot consume or advance to a later candidate until the failure policy permits it.
- [ ] A rejected identity is never evaluated again in the same run, and the fixed Candidate Set is never replenished from the live queue.
- [ ] Public-flow tests cover healthy admission, every eligibility rejection, canonical score agreement and mismatch, the legacy exception, an above-threshold score edit, a below-threshold edit, a relation beyond the first page, zero-effect rejection, and bounded backfill.

## 11. Generate one Resume only from admitted source versions

**What to build:** Make one admitted candidate's Requirements, Draft, human-facing identity, rendering inputs, and canonical artifact documents derive exclusively from the run's fixed Master Resume Version and that candidate's fixed Resume Candidate Source Version.

**Blocked by:** [Admit one candidate before any spend](#10-admit-one-candidate-before-any-spend).

- [ ] Fit Requirement extraction receives only the fixed Master Resume Version and admitted Candidate Source Version as source evidence.
- [ ] Resume Draft generation receives the same fixed source versions plus the validated Requirements result; no live source reload can replace an input.
- [ ] Artifact naming, human-facing download naming, rendering, and canonical Resume and Note documents use the fixed Company, Role, and other admitted values.
- [ ] Prepared provider-request evidence and deterministic artifact evidence can prove that both stages and the artifact documents came from the same fixed source-version pair without retaining private content in safe metadata.
- [ ] A later Master Resume edit never changes an accepted run's provider inputs or output when its exact fixed version remains provable.
- [ ] A later Application edit never mixes a replacement field into already admitted Requirements, Draft, naming, rendering, or artifact content.
- [ ] Unrelated Application management-field edits do not alter the generated source bundle.
- [ ] The persisted Applications-owned Match Score controls admission only and is never recomputed, repaired, or overwritten against the run's Master Resume Version.
- [ ] The Resumes-owned Resume Fit Score and evidence gate remain distinct from the Application Match Score.
- [ ] Insufficient Resume evidence may reject the candidate and permit bounded backfill without changing its Application Match Score, Candidate Source Version, or fixed-set position.
- [ ] The existing public-flow acceptance seam proves coherent fixed-source inputs across both provider stages and artifact-document preparation under deterministic mid-flow workspace mutations.

## 12. Guard every paid dispatch with source revalidation

**What to build:** Put a full Resume Candidate Continuation Check directly in front of every initial or recovery provider authorization, so Merida never reserves or transmits another paid call after a candidate's evidence or eligibility has definitely changed.

**Blocked by:** [Generate one Resume only from admitted source versions](#11-generate-one-resume-only-from-admitted-source-versions).

- [ ] A full Continuation Check guards the initial Requirements authorization and every later Requirements or Draft initial and recovery authorization.
- [ ] Each check obtains a Stable Resume Source Observation and revalidates readability, To Apply, Analyzed, the Match Score threshold and agreement rule, complete required source, and the active Job-Specific Resume relation.
- [ ] Company, Role, accepted Match Score, Job Content, and Application Analysis must still equal the admitted Resume Candidate Source Version.
- [ ] A definite relevant edit, eligibility loss, independent Resume, or definite source unavailability prevents the next reservation and provider transmission.
- [ ] The candidate is never restarted from edited values, never re-admitted, and never receives a second evaluation in the same run.
- [ ] Earlier verified, active, or indeterminate provider spend and already consumed dispatch slots remain unchanged when a later check stops the candidate.
- [ ] A definitely invalidated candidate earns no Resume Completion and may permit bounded backfill only under the approved failure policy.
- [ ] A timeout, rate limit, server error, moving observation, or other ambiguous evidence fails closed without authorizing a call or advancing to a later candidate.
- [ ] An unrelated management-field edit does not prevent authorization when all eligibility and admitted source values still agree.
- [ ] A live Master Resume edit does not invalidate the candidate while the run's exact fixed Master Resume Version remains provable.
- [ ] Deterministic barriers immediately before every actual provider slot prove that no initial or recovery call can bypass the check, without relying on sleeps or paid provider calls.

## 13. Guard entry into artifact work

**What to build:** Revalidate one candidate after its Draft is valid and immediately before PDF staging, private artifact checkpointing, or any Notion or filesystem artifact effect, so stale or unverifiable source evidence cannot escape into durable artifacts.

**Blocked by:** [Guard every paid dispatch with source revalidation](#12-guard-every-paid-dispatch-with-source-revalidation).

- [ ] A full Stable Resume Source Observation and Continuation Check runs after the validated Draft and before the first artifact effect.
- [ ] PDF staging, artifact-checkpoint persistence, Resume creation, Note creation, PDF publication, and relation mutation cannot begin before this barrier succeeds.
- [ ] A relevant source edit, eligibility loss, independent active Resume, or definite source unavailability produces no new artifact effect and no Resume Completion.
- [ ] Ambiguous or moving workspace evidence produces no artifact effect and cannot advance the run to another candidate until the approved failure policy permits it.
- [ ] Earlier provider spend and consumed dispatch slots remain committed according to their existing evidence; stopping before artifacts never manufactures a refund.
- [ ] No current workspace value is mixed into the validated Draft, names, rendered PDF, Resume document, or Note document at this boundary.
- [ ] Unrelated management-field edits pass the barrier when all eligibility and admitted source values still agree.
- [ ] A successful barrier hands the exact fixed-source document bundle to the run-owned artifact workflow selected by the artifact-recovery decision.
- [ ] Restart or recovery of an already-started Artifact Set remains governed by same-run artifact evidence and does not use this barrier to recreate provider output.
- [ ] Public-flow tests place deterministic mutations after Draft validation and prove zero artifact effects for each unsafe or ambiguous observation and normal artifact entry for a safe observation.

## 14. Recover the run's exact Master Resume Version

**What to build:** Let a fresh application instance reclaim an unfinished Resume Run only after proving the exact Master Resume Version selected at creation, without rerunning selection or silently adopting current workspace content.

**Blocked by:** [Start a run from one fixed Master Resume Version and Candidate Set](#9-start-a-run-from-one-fixed-master-resume-version-and-candidate-set) and [Recover Resume spend without manufacturing budget](#6-recover-resume-spend-without-manufacturing-budget).

- [ ] Worker reclaim proves or recovers the run's exact Master Resume Version before candidate admission, provider authorization, or artifact work can continue.
- [ ] Recovery uses the private source-proof mechanism chosen by the durability prototype and does not infer identity from a title, active flag, timestamp, replacement page, or similar content.
- [ ] Editing, archiving, replacing, duplicating, unsharing, or deleting the live selected page never causes a different Master version to be substituted.
- [ ] When the exact fixed version remains provable, live Master page mutation does not implicitly cancel or revoke the run.
- [ ] When the exact fixed version cannot be proven, all dependent candidate work remains blocked under the approved failure policy.
- [ ] Missing or corrupt required proof is distinguishable from a definite live-source change and never triggers a new Master selection.
- [ ] Master Source Checkpoint recovery authenticates the checkpoint kind, schema, run identity, source proof, and key version before exposing its private content; failed authentication exposes no plaintext and starts no dependent work.
- [ ] Recovery never reruns run creation, changes the fixed Candidate Set, changes its order, or chooses a newer Master Resume.
- [ ] Explicit Resume Run cancellation remains the operator's stop signal; source-page mutation is not treated as cancellation.
- [ ] Source proof and recovery diagnostics preserve the privacy boundary and expose no Master Resume content in public run metadata or logs.
- [ ] Fresh-instance tests cover restart before the first candidate, between candidates, between provider stages, and before artifact work with unchanged, edited, unavailable, replacement, missing-proof, and corrupt-proof Master evidence.

## 15. Recover an admitted candidate without source substitution

**What to build:** Resume an admitted candidate after process restart only from its exact fixed Candidate Source Version and current safe continuation state, preserving paid-call and artifact progress without evaluating the identity again or mixing in edited Application data.

**Blocked by:** [Guard entry into artifact work](#13-guard-entry-into-artifact-work) and [Recover the run's exact Master Resume Version](#14-recover-the-runs-exact-master-resume-version).

- [ ] Fresh-instance recovery proves the run's exact Master Resume Version and the admitted candidate's exact Resume Candidate Source Version before continuing dependent work.
- [ ] An unchanged, provable candidate resumes only at its durable next provider or artifact boundary and does not repeat completed or possibly completed work.
- [ ] Recovery obtains the current Stable Resume Source Observation and applies the same Continuation Check required during uninterrupted execution.
- [ ] A definite relevant edit invalidates the admitted candidate; recovery never re-admits it from current content or grants a second evaluation.
- [ ] Definite eligibility loss, definite unavailability, or an independent Resume prevents further candidate work and follows the approved candidate disposition and bounded-backfill policy.
- [ ] Ambiguous source proof or workspace evidence fails closed without provider or artifact work and without advancing to a later candidate.
- [ ] Unrelated management-field edits do not block recovery when all admitted source and eligibility values still agree.
- [ ] A later unadmitted identity in the fixed Candidate Set may capture its own current Candidate Source Version only when the run's exact Master Resume Version remains provable.
- [ ] Recovery preserves all committed spend, dispatch-attempt consumption, durable artifact intent, and earlier Resume Completions rather than reconstructing progress optimistically.
- [ ] Recovery never reruns provider generation to reconstruct missing artifact content and never substitutes current source into a same-run Artifact Set.
- [ ] A valid Requirements result atomically records output validity and spend settlement or Indeterminate billing, then stores one protected Draft Basis Checkpoint containing the exact versioned Resume Draft Input needed for Draft without retaining source bodies, prompts, reasoning, or a raw provider response.
- [ ] The Draft Basis Checkpoint is authenticated to the run, candidate, both source proofs, producing Requirements call, Draft-input schema, matching and evidence-selection policy, and renderer version; a fresh application can prepare the identical Draft call without replaying Requirements.
- [ ] Missing, corrupt, wrongly bound, or undecryptable Draft Basis content never triggers Requirements replay or current-source substitution and follows the approved Candidate-Scoped protected-state failure policy.
- [ ] Deterministic fresh-composition tests cover restart after admission, between Requirements and Draft, after a validated Draft, and before artifact entry for unchanged, changed, unavailable, ambiguous, and unrelated-edit observations.

## 16. Gate the relation-last Resume commit

**What to build:** Immediately before the final Resume-to-Application relation mutation, revalidate the complete candidate source and eligibility state and prove the exact same-run artifact set, so independent or conflicting workspace work can never be adopted or joined.

**Blocked by:** [Guard entry into artifact work](#13-guard-entry-into-artifact-work).

- [ ] The Resume Completion Gate performs one full Stable Resume Source Observation and Continuation Check immediately before the relation-last mutation.
- [ ] The gate validates the complete run-owned Resume, Resume Fit Analysis Note, and PDF set using the ownership evidence selected by the artifact-recovery decision.
- [ ] The Application must still match its admitted Candidate Source Version and satisfy every admission eligibility rule.
- [ ] Complete relation evidence must show no different active Job-Specific Resume before this run attempts attachment.
- [ ] A different independently created Resume is never adopted, modified, archived, detached, or counted and this run never attaches its Resume beside it.
- [ ] An already attached exact run-owned Resume is accepted only as a same-run recovery observation backed by exact ownership and complete-artifact proof.
- [ ] Titles, company, role, filenames, timestamps, content similarity, and an existing relation are never sufficient same-run ownership evidence.
- [ ] Relevant source change, eligibility loss, definite unavailability, ambiguous observation, invalid artifact proof, or conflicting relation state prevents the relation mutation and Resume Completion.
- [ ] Run-owned partial effects follow the artifact decision's recovery, strict compensation, or quarantine behavior without this ticket inventing an alternate cleanup path.
- [ ] Deterministic barriers cover source mutation, an independent Resume appearing, incomplete relation pagination, ambiguous reads, valid same-run recovery, and the clean relation-last path.

## 17. Verify and seal Resume Completion after attachment

**What to build:** Re-read the complete Application state after the unavoidable relation write and record one immutable Resume Completion only when the exact run-owned Resume is the sole active relation and every source and eligibility value still matches the admitted version.

**Blocked by:** [Recover an admitted candidate without source substitution](#15-recover-an-admitted-candidate-without-source-substitution) and [Gate the relation-last Resume commit](#16-gate-the-relation-last-resume-commit).

- [ ] After the relation mutation, Merida obtains another full Stable Resume Source Observation rather than checking only the Resume relation.
- [ ] Completion requires every current eligibility and relevant source value to equal the admitted Resume Candidate Source Version.
- [ ] Completion requires the exact run-owned Resume to be the sole active Job-Specific Resume relation and the complete same-run Artifact Set to remain valid.
- [ ] A changed, definitely unavailable, moving, torn, or otherwise ambiguous post-attachment state records no Resume Completion.
- [ ] A wrong, independent, or additional Resume relation records no Completion and is never adopted as this run's work.
- [ ] Recovery from an ambiguous attachment may count only after a fresh full observation proves the exact owned relation and complete same-run artifacts.
- [ ] An absent exact relation may be retried only through the approved same-run relation recovery after the other artifacts and full source gate revalidate.
- [ ] Completion progress and Artifact Set sealing are committed without double-counting, and fresh-instance recovery can converge on the same single result.
- [ ] A successful Completion preserves exact reconstructable Resume, Note, and PDF identities without retaining private source or generated content in public coordination state.
- [ ] Once conclusively recorded, the Resume Completion is immutable run history: later Application, Master, relation, Resume, Note, or PDF mutation never decrements progress, reopens the candidate, or invokes Same-Run Artifact Recovery.
- [ ] Later artifact or relation mutation is treated as out-of-scope historical drift rather than permission for automatic repair or a new Resume Run evaluation.
- [ ] Deterministic end-to-end tests cover clean pre-check and post-check, every post-attachment race class, ambiguous attach recovery, restart before progress commit, exactly-once credit, and later workspace drift through the normal application composition.
- [ ] Workflow, architecture, operations, and public-contract documentation describe fixed source versions, every safety barrier, relation-last verification, and immutable historical Completion without exposing unresolved implementation details.

---

**Failure and cancellation tranche:** Make every Resume Run stop, backfill, recover, compensate, quarantine, or cancel from durable evidence while preserving earlier Resume Completions and honest spend.

**Source:** [Classify Resume Run failures, outcomes, and cancellation](07-classify-resume-run-failures-and-cancellation.md)

Work the **frontier**: [Bound and classify Stable Resume Source Observation recovery](#18-bound-and-classify-stable-resume-source-observation-recovery) starts after paid-dispatch source revalidation. The healthy Artifact Set path then joins the previously specified Completion Gates before partial recovery, candidate backfill, shared-provider stopping, artifact disposition, and cancellation converge on the final taxonomy gate.

## 18. Bound and classify Stable Resume Source Observation recovery

**What to build:** Make every source-dependent Resume Run boundary use one finite observation policy that can prove stable evidence or stop with the precise safe workspace reason, without authorizing paid or artifact work from a torn or ambiguous read.

**Blocked by:** [Guard every paid dispatch with source revalidation](#12-guard-every-paid-dispatch-with-source-revalidation).

- [ ] Resume Run creation, every Resume Candidate Admission, and every Resume Candidate Continuation Check obtain source evidence through the same bounded Stable Resume Source Observation recovery policy rather than treating any single read as authoritative; the policy remains the one observation seam consumed by the later Resume Completion Gates.
- [ ] The first two consecutive complete observations with identical Resume Source Version Proof succeed: `AA` succeeds after two logical attempts and `ABB` succeeds from the second and third attempts.
- [ ] Three complete observations with no consecutive match, including `ABA`, fail with `workspace_observation_unstable` and cannot authorize provider or artifact work.
- [ ] At most three logical observation attempts may begin, beginning an attempt consumes its slot, and any incomplete attempt breaks consecutiveness.
- [ ] Each logical attempt has one 300-second monotonic absolute deadline covering its complete properties, body, relation, pagination, recursion, and transport-recovery graph; deadline exhaustion starts no further constituent request in that attempt.
- [ ] Each retry-safe constituent workspace request makes at most three transport attempts, and constituent recovery never multiplies the logical-observation limit.
- [ ] Incomplete relation or body pagination, cursor cycles, ever-growing pagination, unsupported content or nesting, response-bound exhaustion, timeout, rate limit, server error, and malformed incomplete reads fail the logical attempt closed.
- [ ] Exhaustion containing any incomplete attempt reports `workspace_unavailable` unless an earlier consecutive complete pair already succeeded; elapsed time or repeated absence never becomes proof of source unavailability or change.
- [ ] Explicit workspace access rejection reports `workspace_access_invalid`, while a schema, malformed-success, or locally validated contract mismatch reports `workspace_contract_mismatch`; neither is relabelled as generic unavailability.
- [ ] Exhausted observation recovery while selecting the Master Resume Version rejects start before creating a Resume Run identity, idempotency binding, Resume Candidate Set, reservation, or artifact intent.
- [ ] Exhausted observation recovery after run creation but before a Resume Artifact Set exists is Run-Scoped: the admitted candidate records the same bounded run reason when required, later candidates remain untouched, and earlier Resume Completions remain committed.
- [ ] A failed or ambiguous pre-Artifact observation produces no new reservation, provider transmission, Artifact Set intent, PDF, Notion mutation, relation mutation, or backfill to another candidate.
- [ ] The observation interface distinguishes an authorizing pre-Artifact read from a fenced drain-required read so later cancellation policy can stop scheduling reads without weakening the source, reconciliation, Completion Gate, or compensation checks required for an existing Resume Artifact Set.
- [ ] Deterministic run-start, Admission, Continuation, and fake/recorded-workspace conformance tests cover the complete observation and reason matrix with controlled monotonic time, explicit barriers, no sleeps, and no private source values in snapshots, logs, or safe errors.

## 19. Commit and seal one exact Resume Artifact Set

**What to build:** Integrate the previously specified Resume Completion Gates and seal with the production Resume Artifact Set, checkpoint, Notion, and PDF path so one valid Draft reaches one relation-last Resume Completion with exact ownership and content proof.

**Blocked by:** [Guard entry into artifact work](#13-guard-entry-into-artifact-work), [Gate the relation-last Resume commit](#16-gate-the-relation-last-resume-commit), [Verify and seal Resume Completion after attachment](#17-verify-and-seal-resume-completion-after-attachment), and [Bound and classify Stable Resume Source Observation recovery](#18-bound-and-classify-stable-resume-source-observation-recovery).

- [ ] A candidate with a valid Draft receives one opaque, immutable Resume Artifact Set ID before its first artifact effect, durably bound to the owning Resume Run, candidate ordinal, and Application and never reused.
- [ ] The already-operational production checkpoint vault extends its authenticated identity and binding contract to the Resume Artifact Checkpoint and keeps its canonical Resume and Note documents absent from ordinary coordination, public state, logs, errors, and raw SQLite, WAL, and SHM inspection.
- [ ] One transaction replaces the Draft Basis with Resume Artifact Set intent and a protected Resume Artifact Checkpoint containing the exact validated canonical Resume and Note documents and their Artifact Document Digests.
- [ ] Artifact work follows the canonical order: checkpointed intent, PDF staging, unlinked Job-Specific Resume creation, PDF publication, Resume Fit Analysis Note creation, complete-set validation, relation-last attachment, post-attachment readback, and Resume Completion seal.
- [ ] The Job-Specific Resume and Resume Fit Analysis Note carry the exact Resume Artifact Set ID in their initial properties; the Resume begins unlinked and the Note begins with the exact expected Application and Resume relations.
- [ ] Each Notion page is created synchronously with one complete enhanced-Markdown request containing all initial properties and canonical content, with an Artifact Request Digest over the exact request bytes and no later block append or asynchronous content task.
- [ ] PDF staging renders first to an unowned private temporary file, then records the Resume Artifact Set ID, expected full-ID path, Resume Artifact Document Digest, and PDF Byte Digest before atomically exposing the staged file.
- [ ] Staged and published PDF storage is non-overwriting and addressed by the full Resume Artifact Set ID; the finalized human-facing basename remains presentation metadata and cannot establish ownership.
- [ ] The published PDF index is keyed by Resume Artifact Set ID, may bind the freshly observed Resume identity for lookup, and cannot resolve, overwrite, or remove another candidate's PDF even when names normalize identically.
- [ ] Before attachment, the Resume Completion Gate freshly proves the admitted source, exact sole run-owned Resume, Note, PDF, ownership, relations, semantic document digests, PDF bytes, and reconstructable result identities.
- [ ] After attachment, a second complete Stable Resume Source Observation proves that the exact run-owned Resume is the sole active Job-Specific Resume relation and that every source and eligibility value still matches the admitted Resume Candidate Source Version.
- [ ] One logical transaction records exactly one Resume Completion, candidate `completed`, terminal sealed Resume Artifact Set evidence, run progress, compact reconstructable result identities, and `target_met` when this seal first reaches the Resume Batch Target.
- [ ] Replayed or concurrent sealing cannot double-count, replace the result identities, reopen the candidate, or rewrite an already won Resume Run Outcome or reason.
- [ ] Resume Artifact Checkpoint deletion occurs only after the seal as idempotent cleanup; deletion failure leaves the Completion sealed and may never reopen, recount, or compensate it.
- [ ] The approved public Resume Run seam completes one healthy candidate through the real Resumes-owned transaction/checkpoint store and filesystem artifact implementation, while snapshots and durable safe metadata expose no checkpoint documents, source content, provider payload, reasoning, filesystem path, or transient URL.

## 20. Recover one partial Resume Artifact Set forward

**What to build:** Recover one interrupted or ambiguous partial Resume Artifact Set to the same truthful Completion without replaying provider work, duplicating an external effect, replacing its identity, or trusting stale local phase state.

**Blocked by:** [Commit and seal one exact Resume Artifact Set](#19-commit-and-seal-one-exact-resume-artifact-set).

- [ ] A fresh application instance can reclaim one partial Resume Artifact Set at every durable artifact boundary and converge on exactly one Resume Completion with the original Resume Artifact Set ID.
- [ ] Recovery uses fresh Notion and PDF evidence rather than trusting a stale recorded phase, while durable intent and observed evidence constrain which external action may safely occur next.
- [ ] Recovery preserves the original Resume Artifact Checkpoint, canonical Resume and Note documents, digests, fixed source versions, and accepted Draft; it never reruns a provider stage, allocates a replacement identity, or adopts independent artifacts.
- [ ] Recovery rechecks invariants in canonical effect order and performs only the earliest missing safe effect, even when a later effect is unexpectedly visible.
- [ ] Every Notion, PDF, or relation effect has at most two durable mutation attempts across uninterrupted execution and restart, with one external mutation transmission per attempt and no hidden write retry.
- [ ] A second mutation attempt requires affirmative non-dispatch or fresh proof that an idempotently repeatable desired state is absent while every prerequisite still holds; an ambiguous Resume or Note creation is never automatically resent.
- [ ] An ambiguous Resume or Note creation receives exactly one immediate bounded exact-ID reconciliation pass across all active and archived matches; one uniquely valid page is preserved, while zero, multiple, truncated, unknown, or mismatched results enter Resume Artifact Quarantine.
- [ ] A previously observed Resume or Note that is missing, archived, structurally changed, relation-mismatched, or digest-mismatched enters Resume Artifact Quarantine and is never replaced.
- [ ] Valid write-ahead evidence with a missing staged PDF permits deterministic rerender from the same checkpoint and must reproduce the expected digests; unowned temporary residue is ignored, while a final staged path without matching prior evidence or any byte mismatch quarantines the Resume Artifact Set.
- [ ] A complete valid Resume Artifact Set with an absent final relation may attach or safely repeat the relation only after both Resume Completion Gates revalidate; a lost attach response seals only after fresh readback proves the exact sole relation.
- [ ] A missing or corrupt required Resume Artifact Checkpoint while effects remain produces zero provider calls and retains the Application-scoped Resume Artifact Quarantine rather than regenerating content or guessing cleanup.
- [ ] Every Artifact Set reconciliation pass has one 300-second monotonic absolute deadline covering its complete exact-ID lookup and readback graph, including active and archived pagination, recursive content retrieval, and constituent transport attempts.
- [ ] Loss of provider or spend authority after the Resume Artifact Set exists does not block deterministic forward recovery or sealing unless another provider call is actually required.
- [ ] Freshly reconstructed Resume, Note, and PDF result identities come only from verified Artifact Set evidence and remain available after cached response objects and process memory are discarded.
- [ ] One focused artifact-workspace conformance suite runs against both the deterministic workspace and recorded Notion adapter and proves exact-ID lookup, archived cardinality, enhanced-Markdown creation and readback, semantic normalization, lost-response reconciliation, mutation error normalization, relation-last behavior, and compensation barriers.
- [ ] The restart matrix proves no duplicate external effect, no replacement page, no provider replay, exactly-once Completion, checkpoint retention through partial recovery or quarantine, and privacy-safe state using explicit crash barriers rather than timing sleeps.

## 21. Backfill after definitive pre-Artifact candidate stops

**What to build:** Let one Resume Run skip or fail a definitively unsuitable candidate and continue with the next fixed identity only after the candidate reaches a safe pre-Artifact boundary, preserving exact evaluation, spend, and exhaustion semantics.

**Blocked by:** [Bound and classify Stable Resume Source Observation recovery](#18-bound-and-classify-stable-resume-source-observation-recovery) and [Commit and seal one exact Resume Artifact Set](#19-commit-and-seal-one-exact-resume-artifact-set).

- [ ] Resume Run creation excludes every Application already under active Resume Artifact Quarantine without changing the canonical ordering of the remaining fixed Resume Candidate Set.
- [ ] Quarantine that appears after the fixed snapshot but before Resume Candidate Admission records `skipped` with `artifact_quarantine_active`, consumes no evaluation, starts no source Admission or provider work, and does not replenish the fixed slot.
- [ ] A definite Resume Candidate Admission rejection atomically consumes that identity's one evaluation, records `skipped`, and selects exactly the first applicable reason in this order: `application_unavailable`, `application_not_to_apply`, `application_not_analyzed`, `match_score_missing`, `match_score_below_threshold`, `analysis_score_mismatch`, `candidate_source_incomplete`, `independent_resume_exists`.
- [ ] A definite post-admission source or eligibility stop records `failed` with exactly one of `candidate_source_unavailable`, `candidate_became_ineligible`, `candidate_source_changed`, or `independent_resume_created`, without substituting current source or granting another evaluation.
- [ ] Insufficient evidence, a stage-specific context overflow, exhausted unusable Requirements or Draft output, or an isolated Draft Basis Checkpoint defect records the corresponding bounded Candidate-Scoped reason and never hides it behind a generic failure.
- [ ] Requirements or Draft output becomes Candidate-Scoped exhaustion only after both stage attempts are consumed by unusable output; shared retryable provider exhaustion, mixed provider recovery exhaustion, and authorization defects remain Run-Scoped and never authorize backfill.
- [ ] A pre-Artifact skip or Candidate-Scoped Failure creates no Resume Artifact Set effect, retires any Draft Basis Checkpoint only after its definitive terminal decision commits, and cannot restore a consumed provider attempt or previously committed spend.
- [ ] Ambiguous workspace evidence, an active provider call, or unfinished automatic mutation is never treated as a definitive candidate stop and cannot authorize backfill merely because time passes.
- [ ] After the candidate reaches its safe terminal boundary, the worker selects only the next pending identity in the immutable Resume Candidate Set, never reevaluates a terminal identity, appends a live-queue identity, changes order, or exceeds the Resume Attempt Budget.
- [ ] Backfill continues only while the Resume Batch Target is unmet and no run-stopping decision has won; `spend_limited`, `cancelled`, `authorization_blocked`, or Run-Scoped `failed` leaves every later identity pending.
- [ ] Candidate state and reason remain independent of provider-call accounting: `skipped` and `failed` each carry exactly one semantic reason, while verified, active, released, or Indeterminate spend evidence remains truthful.
- [ ] A run whose later candidate completes can finish `target_met` while preserving the earlier skipped or failed candidate, exact evaluated/skipped/failed/completion counters, and every prior Resume Completion.
- [ ] Exhausting the fixed set without an earlier stop records `attempt_budget_exhausted` only when run-start eligibility was truncated at twice the target; otherwise it records `queue_exhausted`, and later queue mutations cannot rewrite the outcome.
- [ ] Table-driven public-flow tests cover every pre-Artifact skip and Candidate-Scoped Failure reason, multi-defect precedence, zero forbidden effects, exact evaluation consumption, successful bounded backfill, both exhaustion outcomes, restart equivalence, and privacy-safe serialization.

## 22. Stop a Resume Run on shared provider and authorization defects

**What to build:** Stop one Resume Run at the correct shared boundary when provider recovery or authorization is unsafe, distinguishing valid spend limitation, unusable candidate output, shared provider failure, and conservative Indeterminate billing without sacrificing earlier work.

**Blocked by:** [Backfill after definitive pre-Artifact candidate stops](#21-backfill-after-definitive-pre-artifact-candidate-stops).

- [ ] Provider and spend readiness is checked before run creation and immediately before every initial or recovery provider authorization; a start-time defect rejects the start without creating a Resume Run.
- [ ] Provider and spend authority is required only when another provider call could be authorized; an existing Resume Artifact Set may recover, compensate, quarantine, or seal without live provider authority.
- [ ] Authentication, insufficient balance, unavailable spend authority, Resume Generation Envelope mismatch, unavailable or expired approvals, unapproved model, unavailable tokenizer, and unapproved protocol overhead stop immediately as `authorization_blocked` with their exact approved reason and no provider retry.
- [ ] Rejection of a locally valid request, provider protocol failure, returned-model contradiction, and usage or pricing contradiction stop before another candidate or provider call with their exact approved reason.
- [ ] A returned-model contradiction invalidates output, while missing matching billing evidence alone creates an Indeterminate Resume Call and does not invalidate otherwise usable output.
- [ ] Contradictory usage or pricing retains conservative spend and prevents another authorization even when the returned output is independently usable.
- [ ] Exhausting both stage attempts entirely on rate limiting, provider unavailability, or transport failure finishes the run as `failed` with the corresponding homogeneous exhaustion reason.
- [ ] Exhausting both attempts on a mixture of retryable shared-provider defects and unusable output finishes the run as `failed` with `provider_recovery_exhausted`.
- [ ] Two attempts containing only empty, truncated, malformed, or semantically invalid output remain Candidate-Scoped and do not become a shared provider failure.
- [ ] A valid-context call whose exact reservation cannot fit finishes as `spend_limited`; invalid provider or spend authority is never reported as ordinary budget exhaustion.
- [ ] The admitted current candidate records the safe run reason when shared failure stops it before a Resume Artifact Set exists, while untouched candidates remain `pending` and earlier Resume Completions remain immutable.
- [ ] The first committed stopping decision and reason remain fixed if target, spend, exhaustion, cancellation, or another defect is observed later.
- [ ] Every provider and authorization reason is selected in the approved deterministic order and contains no provider text, exception details, dynamic identity, or private Resume content.
- [ ] Prepared-provider contract tests and composed Resume Run tests cover every reachable attempt sequence, every immediate defect, usable output with Indeterminate billing, exact stopping scope, zero later dispatch, restart, and preservation of earlier work.

## 23. Compensate or quarantine a stopped Resume Artifact Set

**What to build:** Bring a definitively stopped Resume Artifact Set to a safe boundary by reversing only exact run-owned effects when proof permits it and imposing durable Resume Artifact Quarantine whenever ownership, effect, or cleanup remains uncertain.

**Blocked by:** [Recover one partial Resume Artifact Set forward](#20-recover-one-partial-resume-artifact-set-forward) and [Stop a Resume Run on shared provider and authorization defects](#22-stop-a-resume-run-on-shared-provider-and-authorization-defects).

- [ ] Once a Resume Artifact Set exists, a definitive condition that makes Resume Completion impossible starts strict compensation only when every affected run-owned artifact and relation is unambiguously identifiable.
- [ ] Compensation mutates only artifacts proved to belong to the exact Resume Artifact Set and never adopts, modifies, archives, detaches, or deletes an independent or ambiguously owned artifact.
- [ ] Strict compensation proceeds through the canonical verified reverse barriers: clear the owned Resume relation, archive the owned Note, remove the published PDF, archive the owned Resume, then remove staged residue and the active lookup entry.
- [ ] Each compensation barrier records durable intent before mutation and durable observed evidence afterward, uses at most two durable attempts, and performs at most one external mutation transmission per attempt.
- [ ] A later compensation attempt is permitted only after affirmative non-dispatch or fresh proof that an idempotently repeatable desired state remains absent while every prerequisite still holds.
- [ ] Failure or ambiguity while verifying one reverse barrier stops cleanup before any lower effect is changed and places the Artifact Set under Resume Artifact Quarantine with `artifact_compensation_unproven`.
- [ ] Uncertain ownership, content, relation state, result reconstruction, mutation outcome, or cleanup uses the corresponding approved quarantine reason rather than inventing completion or terminal compensation.
- [ ] Quarantine remains orthogonal to failure scope: an isolated candidate defect permits bounded backfill only after automatic mutation has stopped, while a demonstrated shared workspace, rendering, storage, checkpoint, or authority defect also stops the Resume Run.
- [ ] A Resume Artifact Set under potentially sealable Resume Artifact Quarantine keeps its candidate `recovering`; compensation-only quarantine may coexist with terminal `failed` or `cancelled` and cannot later seal.
- [ ] During active reversal the candidate is `compensating` with the definitive failure reason, then becomes `failed` only after verified compensation or after cleanup uncertainty is durably quarantined with automatic mutation stopped.
- [ ] Deterministic PDF rejection follows zero-effect compensation: Merida proves that no owned staged or published file, page, relation, or lookup entry exists before recording `pdf_render_rejected` and retiring the Resume Artifact Checkpoint.
- [ ] Restart resumes from the first unverified compensation barrier with the same Resume Artifact Set ID and checkpoint; it never regenerates provider output, allocates replacement artifact identities, or repeats a verified mutation.
- [ ] Every quarantine retains the checkpoint and key needed for later evidence-backed resolution and enforces the Application-scoped mutation lock across restart, lease loss, cancellation, and owning-run completion.
- [ ] Composed workflow, workspace, PDF, and store tests cover every forward-effect and reverse-barrier failure under success, definite conflict, affirmative non-dispatch, lost response, ambiguous readback, unavailable reconciliation, shared infrastructure loss, and restart.

## 24. Let isolated Resume Artifact Quarantine resolve without rewriting the run

**What to build:** Allow an isolated Resume Artifact Quarantine to stop holding the batch open while preserving its mutation lock, then let audited evidence recover, seal, or compensate that exact set without rewriting why its owning Resume Run finished.

**Blocked by:** [Compensate or quarantine a stopped Resume Artifact Set](#23-compensate-or-quarantine-a-stopped-resume-artifact-set).

- [ ] Resume Artifact Quarantine survives time passage, restart, lease loss, and owning-run completion until an audited reconciliation proves an allowed exit; cancelled-run integration is exercised after cancellation exists.
- [ ] A generic acknowledgement never authorizes mutation, removes the Application-scoped mutation lock, changes candidate state, or changes the owning Resume Run.
- [ ] Audited reconciliation uses the exact Resume Artifact Set ID and freshly validates complete ownership, content, digest, relation, cardinality, source, and result evidence.
- [ ] Affirmative non-dispatch evidence may return the original Artifact Set to Same-Run Artifact Recovery without allocating a replacement identity or repeating provider generation.
- [ ] Fresh proof of one valid committed Resume Artifact Set may proceed through the mandatory Resume Completion Gates and the existing atomic Completion seal.
- [ ] Fresh proof of exact ownership plus controlled mutation authority may enter strict compensation, which must complete and verify every owned effect before the Application is unblocked.
- [ ] A candidate with a Resume Artifact Set under potentially sealable Resume Artifact Quarantine remains `recovering` after its Resume Run finishes and becomes `completed` only when the audited seal records one immutable Resume Completion.
- [ ] A compensation-only quarantine cannot later seal; it retains the candidate's factual terminal disposition until strict verified compensation resolves the mutation lock.
- [ ] A late Resume Completion changes the truthful Completion count and candidate disposition but never rewrites the previously committed Resume Run Outcome or reason.
- [ ] Late Completion may bring the count to or above the Resume Batch Target, but it cannot authorize another candidate, reopen the queue, restore an evaluation, or exceed the fixed Resume Candidate Set bound.
- [ ] An isolated quarantine permits normal bounded backfill once automatic mutation has stopped, while a shared defect retains the previously selected run-stopping decision.
- [ ] The single-active-run claim may be released while Application-scoped quarantine persists once every automatic mutation has stopped and all other safe-drain conditions hold.
- [ ] The required Resume Artifact and Master Source Checkpoints and key versions remain available while resolution is possible and retire only after a proved Completion seal or fully verified compensation.
- [ ] Deterministic composed tests cover all three audited exits, unresolved quarantine across restart, late seal after each relevant terminal outcome, Completion counts equal to and above target, immutable outcome and reason, independent-artifact rejection, checkpoint retention, and eventual mutation-lock release.

## 25. Cancel queued and pre-Artifact Resume work safely

**What to build:** Let the operator cancel before a Resume Artifact Set is established, stopping every later admission and provider call while settling an already-marked call honestly and preserving the exact state needed if a valid marked Draft crosses into artifact recovery.

**Blocked by:** [Stop a Resume Run on shared provider and authorization defects](#22-stop-a-resume-run-on-shared-provider-and-authorization-defects).

- [ ] Cancellation is idempotent through the approved public Resume Run boundary for queued, running, cancelling, and finished runs; cancelling a finished run returns its existing terminal snapshot unchanged.
- [ ] A successful cancellation transaction atomically records `cancelled` with `operator_cancelled` and the forward scheduling barrier; repeated cancellation observes that same decision without duplicating any state transition.
- [ ] Queued cancellation atomically finishes without consuming an evaluation, provider attempt, reservation, spend, or artifact effect; every candidate remains `pending`, the unused Master Source Checkpoint retires, and the idempotency record remains available.
- [ ] Cancellation committed before a Resume Candidate Admission disposition leaves the candidate `pending` and consumes no evaluation, even when the already-started remote observation later returns.
- [ ] During a pre-Artifact scheduling observation, cancellation permits the currently executing retry-safe request to return but begins no later transport attempt, constituent request, pagination request, or logical observation and allows returned evidence to authorize no Admission or provider work.
- [ ] Admission committed before cancellation remains one consumed evaluation with its fixed Resume Candidate Source Version; cancellation before the next call's may-have-dispatched marker makes that candidate `cancelled` with `operator_cancelled`.
- [ ] Cancellation committed before the may-have-dispatched marker forbids transmission; affirmative non-dispatch releases an existing reservation but never restores the consumed stage attempt.
- [ ] A may-have-dispatched marker committed first keeps the provider call in flight until its normal bounded response or timeout; cancellation does not actively abort it or manufacture proof that it was unsent.
- [ ] Every in-flight call settles trustworthy billing evidence independently, while missing trustworthy evidence retains the complete reservation as an Indeterminate Resume Call.
- [ ] A Requirements result arriving after cancellation never authorizes Draft: a previously committed Draft Basis Checkpoint retires, a cancellation-first result creates no private checkpoint, and every result class converges on candidate state `cancelled`.
- [ ] A usable Draft whose dispatch marker won atomically settles or retains its reservation, replaces the Draft Basis with the exact Resume Artifact Set and Resume Artifact Checkpoint, and hands the candidate to Same-Run Artifact Recovery without requiring another provider authorization.
- [ ] An unusable or unresolved Draft result after cancellation starts no recovery call, retires the Draft Basis Checkpoint, and leaves the candidate `cancelled` while preserving all honest call and spend evidence.
- [ ] Cancellation starts no later Resume Candidate Admission, provider call, or backfill candidate; untouched fixed-set entries remain `pending`, and every earlier Resume Completion remains immutable.
- [ ] Deterministic fresh-composition tests place cancellation barriers around Admission, every observation request, reservation, may-have-dispatched marker, every Requirements and Draft result class, Draft-to-Artifact transition, worker reclaim, and restart, proving exact candidate state, spend disposition, checkpoint retirement, dispatch count, and immutable stopping order.

## 26. Drain cancellation through an established Resume Artifact Set

**What to build:** Finish a cancelled Resume Run from an already-accepted Draft or partial Resume Artifact Set by recovering forward, compensating exact owned effects, or durably quarantining uncertainty before releasing the active-run claim.

**Blocked by:** [Compensate or quarantine a stopped Resume Artifact Set](#23-compensate-or-quarantine-a-stopped-resume-artifact-set) and [Cancel queued and pre-Artifact Resume work safely](#25-cancel-queued-and-pre-artifact-resume-work-safely).

- [ ] Cancelling a running Resume Run records `cancelled` with `operator_cancelled`, preserves every prior Resume Completion and all verified, active, and indeterminate spend, and leaves the lifecycle `cancelling` until safe drain completes.
- [ ] When a Draft call crossed its may-have-dispatched marker before cancellation, a subsequently returned valid Draft may atomically establish its original Resume Artifact Set and protected checkpoint even when its billing remains Indeterminate; an unusable result starts no recovery call and retires the Draft Basis.
- [ ] Once a Resume Artifact Set exists, cancellation continues the canonical forward path with the same immutable Resume Artifact Set ID and checkpoint: PDF staging or deterministic rerender, Resume reconciliation or creation, PDF publication, Note reconciliation or creation, complete-set validation, relation attachment and readback, and the logical Completion seal.
- [ ] Cancellation-driven recovery never reruns provider generation, allocates a replacement Resume Artifact Set ID, recreates an ambiguously created Resume or Note, or adopts an independent artifact.
- [ ] Bounded, lease-fenced source observations, exact-ID artifact reconciliation, readback, Resume Completion Gates, and compensation verification remain available during drain, but none can authorize another candidate or provider call.
- [ ] Provider and spend authority becoming unavailable after the Resume Artifact Set exists does not block deterministic recovery, compensation, quarantine, or sealing unless another provider call would actually be required.
- [ ] Every drain mutation retains durable intent and evidence, the accepted one-transmission-per-effect-attempt rule, the two-attempt ceiling where repeat is permitted, and fencing that prevents a stale worker from dispatching or committing later work.
- [ ] A fully valid drained Resume Artifact Set passes both Resume Completion Gate observations and seals exactly once; the candidate becomes `completed`, while the already-recorded Resume Run Outcome remains `cancelled` even if the Completion count now equals the target.
- [ ] A definite source, ownership, content, digest, relation, or independent-Resume conflict switches only the exact run-owned effects into strict verified compensation; the candidate is `compensating` until every reverse barrier proves success and then becomes `failed` with the definitive cause.
- [ ] Cancellation during strict compensation never pauses reversal; an unproved cleanup barrier stops further mutation and records compensation-only Resume Artifact Quarantine rather than guessing that cleanup succeeded.
- [ ] Uncertain ownership, effect, readback, or completion evidence records durable Resume Artifact Quarantine with automatic mutation stopped; a potentially sealable set remains `recovering`, while compensation-only quarantine may coexist with a terminal `failed` or `cancelled` candidate.
- [ ] Restart at every artifact intent, dispatch, observation, Resume Completion Gate, seal, and compensation boundary converges on the same factual disposition without duplicate provider calls, pages, files, relations, reversals, or Completion credit.
- [ ] Deterministic cancellation barriers immediately before and after PDF staging, every artifact intent, mutation, and observation, both Resume Completion Gates, relation attachment, the Completion seal, quarantine, compensation, and worker claim prove exactly which fenced drain action may still begin.
- [ ] The run reaches `finished` and atomically releases its single-active-run claim only when no provider call remains locally active, every started mutation has durable observed evidence or durable Resume Artifact Quarantine, and the current Artifact Set is sealed, fully compensated, or quarantined with automatic mutation stopped.
- [ ] A long-lived Application-scoped quarantine may survive the cancelled finished run without retaining or reacquiring the run claim; audited post-run resolution is joined with cancellation in the stopping-race ticket.

## 27. Preserve the first Resume Run stopping decision through races

**What to build:** Make every competing target, cancellation, spend, authorization, exhaustion, and failure stop resolve by durable transaction order, preserving one immutable Outcome and reason while truthful settlement and safe drain continue.

**Blocked by:** [Let isolated Resume Artifact Quarantine resolve without rewriting the run](#24-let-isolated-resume-artifact-quarantine-resolve-without-rewriting-the-run) and [Drain cancellation through an established Resume Artifact Set](#26-drain-cancellation-through-an-established-resume-artifact-set).

- [ ] One serialized transaction records the first Resume Run Outcome and its compatible semantic reason, and no later cancellation, target observation, spend result, authorization loss, exhaustion, or failure can rewrite either value.
- [ ] The target-reaching Resume Completion, updated Completion count, Resume Artifact Set seal, and `target_met` stopping decision commit atomically; no observable state can contain the target-reaching Completion without its target outcome or vice versa.
- [ ] Deterministic barriers exercise both commit orders for cancellation versus `target_met`, `spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `authorization_blocked`, and Run-Scoped `failed`, proving that the transaction that commits first wins in every pairing.
- [ ] A cancellation request that loses a stopping race is an idempotent no-op returning the existing run; a cancellation decision that wins remains `cancelled` through all later settlement, recovery, compensation, quarantine, and sealing.
- [ ] A run-stopping provider, workspace, artifact, checkpoint, storage, or execution failure encountered during candidate work wins over later incidental Resume Candidate Set exhaustion.
- [ ] Provider and spend authority are evaluated before exact reservation fit, so invalid authority produces `authorization_blocked` and `spend_limited` is possible only for an otherwise valid exact call.
- [ ] `attempt_budget_exhausted` and `queue_exhausted` are selected only after no candidate remains active and no earlier stopping condition exists; the immutable run-start queue-truncation fact deterministically distinguishes the two.
- [ ] The winning stopping decision may precede `finished` while bounded call settlement, Resume Artifact Set recovery, compensation, or quarantine reaches safe drain; no extra paused, stopping, or recovering Resume Run lifecycle is introduced.
- [ ] Truthful Completion and spend counters may continue to settle after the stopping decision without changing its Outcome or reason, including a cancelled run that reaches its target and a quarantined late Completion that reaches or exceeds it.
- [ ] Audited proof may seal a Resume Artifact Set under potentially sealable Resume Artifact Quarantine after a cancelled run finishes, updating truthful Completion history without reacquiring the run claim or rewriting `cancelled` and `operator_cancelled`.
- [ ] The current candidate records its factual result rather than blindly mirroring the run: a pre-Artifact admitted candidate stopped by cancellation becomes `cancelled`, another pre-Artifact run stop records `failed` with the run reason, and an existing Resume Artifact Set becomes completed, failed, or recovering according to drain.
- [ ] Restart and lease reclaim preserve the same winning stop transaction, candidate disposition, counters, and remaining drain work; stale workers cannot commit a competing decision or duplicate a Resume Completion seal.
- [ ] The single-active-Resume-Run claim remains held after the stopping decision until safe drain and is released atomically with `finished`, preventing a new run from overlapping unresolved automatic work.
- [ ] Repeated observation, cancellation, and recovery after `finished` returns the same immutable Outcome and reason and never reopens a terminal candidate, restores an evaluation or attempt, or reclaims the active-run slot.

## 28. Suspend safely through run-store and checkpoint authority loss

**What to build:** Fail closed when Resume Run transaction or protected-checkpoint authority is unavailable, distinguishing what the current worker directly knows from what a fresh worker can prove and never fabricating progress, non-transmission, or a terminal outcome.

**Blocked by:** [Preserve the first Resume Run stopping decision through races](#27-preserve-the-first-resume-run-stopping-decision-through-races).

- [ ] Missing checkpoint-key authority, unusable protected-checkpoint capability, or unavailable transaction authority detected at start readiness rejects the request before creating a Resume Run, idempotency binding, Resume Candidate Set, reservation, or artifact intent.
- [ ] Total Resume Run transaction-store loss suspends the live worker fail closed: it starts no Resume Candidate Admission, provider dispatch, artifact mutation, or compensation mutation and cannot fabricate a terminal outcome it is unable to commit.
- [ ] During suspension, the application exposes no state newer than a safely readable or cached committed snapshot and never converts process-local observations into durable progress, spend release, non-dispatch proof, or failure.
- [ ] A run whose transaction authority never recovers remains durably nonterminal and retains its single-active-run claim rather than pretending that it failed or releasing overlapping work.
- [ ] Calls and artifact effects already beyond a may-have-dispatched marker remain ambiguous through the outage; elapsed time, lease expiry, local cancellation, or a lost response neither releases their reservation nor authorizes a duplicate effect.
- [ ] If the same fenced worker observes transaction-store recovery, it first reconciles every possibly dispatched call and artifact effect from durable identity plus its retained direct evidence, then commits `failed` with `run_store_unavailable` unless an earlier stopping decision already won.
- [ ] If the observing process dies before recording the outage, a fresh worker trusts only durable markers after recovery, does not invent `run_store_unavailable`, and resumes, reconciles, or stops solely from facts it can prove.
- [ ] Capability-level classification is precise when ordinary coordination remains writable: unavailable key authority uses `checkpoint_key_unavailable`, systemic checkpoint operations use `checkpoint_store_unavailable`, and total physical or transaction failure uses `run_store_unavailable`; reason precedence prevents a narrower diagnosis when its prerequisite store capability is not provable.
- [ ] An unavailable or corrupt Master Source Checkpoint is Run-Scoped as `master_checkpoint_unavailable`; recovery never selects a replacement Master Resume Version, and no dependent candidate, provider, or artifact work begins.
- [ ] An isolated unavailable or corrupt Draft Basis Checkpoint before artifact effects ends only that candidate as `failed` with `draft_basis_checkpoint_unavailable`, never replays paid Requirements work, retires unusable private state after the terminal decision, and permits bounded backfill.
- [ ] An isolated unavailable or corrupt Resume Artifact Checkpoint after effects begin records `artifact_checkpoint_unavailable` Resume Artifact Quarantine, performs no provider regeneration or unsafe replacement mutation, stops automatic work for that Application, and permits backfill only after the isolated mutation lock is durable.
- [ ] A systemic checkpoint-store failure blocks every operation that depends on protected state and stops the run as `failed` with `checkpoint_store_unavailable`, while preserving earlier Resume Completions, honest spend, exact artifact identities, and any checkpoint evidence that remains readable.
- [ ] Checkpoint deletion failure after a Resume Completion seal or fully verified compensation never reopens, recounts, or reclassifies the candidate; isolated cleanup may retry idempotently when future checkpoint retention remains provably safe, while systemic loss blocks dependent later work.
- [ ] Fresh-composition tests inject store loss and each checkpoint or key failure before and after Admission, dispatch markers, Draft-to-Artifact transition, every effect, seal, and cleanup, proving zero unsafe dispatch, the correct recovery branch, bounded reason, checkpoint retention or retirement, and no private plaintext in snapshots, logs, or errors.

---

**Operator-contract tranche:** Expose the settled Resume Run and Resume Artifact Set contract through staged, restart-safe vertical slices, build the prototype-approved process console, and perform one atomic public cutover without a dual Resume writer.

**Source:** [Define the operator-visible Resume Run contract](08-define-operator-visible-resume-run-contract.md)

Work the **frontier**: [Prefactor dashboard durable-resource observation plumbing](#29-prefactor-dashboard-durable-resource-observation-plumbing) can start immediately while the durable Resume foundations progress. [Stage retained Resume Run reads](#30-stage-retained-resume-run-reads) begins after store and checkpoint authority loss is safe. Staged Resume Run commands, Artifact Set resources and actions, and verified PDF delivery then converge on the failure-taxonomy proof, the prototype-approved dashboard, and one coordinated public cutover. Until that final cutover, staged Resume routes remain outside the default production router and generated public client so no supported release exposes two Resume writers.

## 29. Prefactor dashboard durable-resource observation plumbing

**What to build:** Preserve the current Analysis Run experience while making dashboard polling and typed-error handling reusable for independently observable Resume Runs and Resume Artifact Sets.

**Blocked by:** None — can start immediately.

- [ ] Existing Analysis Run start, active-run reconnection, polling, cancellation, terminal refresh, and error presentation remain behaviorally unchanged.
- [ ] Polling is keyed by durable resource kind and identity, so an Analysis Run, Resume Run, and Resume Artifact Set can be observed concurrently without one resource cancelling or replacing another resource's scheduled work.
- [ ] At most one request is in flight for each observed resource, while different resources may poll independently.
- [ ] Replacing an observed identity cancels only that identity's obsolete schedule; disposing the dashboard session cancels every outstanding schedule and ignores late responses.
- [ ] Poll continuation and completion are caller-supplied policies rather than hard-coded to Analysis Run lifecycle, allowing Resume Run revision and Artifact Set active-action semantics later.
- [ ] Freshness comparison is resource-specific: existing Analysis behavior retains its lifecycle and timestamp protection, while future revisioned resources can reject stale or out-of-order snapshots by identity and revision.
- [ ] A transient polling failure produces a safe resource-scoped error without erasing the last durable snapshot, starting duplicate polling loops, or stopping observation of unrelated resources.
- [ ] API failures use one shared normalization path that preserves safe code, request ID, active-run identity, and validation failures without parsing human-readable messages.
- [ ] The normalized error shape can later carry a bounded readiness reason and current Artifact Set without introducing a dashboard-local copy of the API wire schema.
- [ ] No Resume command, Resume UI, public route, OpenAPI schema, or generated-client operation is added by this prefactor.
- [ ] Deterministic scheduler tests cover concurrent resources, one-in-flight enforcement, stale responses, transient failure, identity replacement, terminal predicates, and disposal without sleeps.
- [ ] The generated-client freshness check, dashboard typecheck, Analysis presentation tests, and existing public behavior remain green.

## 30. Stage retained Resume Run reads

**What to build:** Let a staged composed API reconstruct and expose one retained Resume Run by ID and rediscover the Active and Latest Resume Runs, without yet changing the supported production route inventory.

**Blocked by:** [Suspend safely through run-store and checkpoint authority loss](#28-suspend-safely-through-run-store-and-checkpoint-authority-loss).

- [ ] One named Resume Run Snapshot exposes exactly the approved identity, revision, lifecycle, immutable stopping decision, timestamps, target, Attempt Budget, progress, spend, and complete fixed Candidate Set.
- [ ] Every candidate exposes only its stable Application identity and label, ordinal, state, stage, bounded reason, evaluation-consumption fact, Artifact Set link, atomic Completion Summary, and durable timestamps.
- [ ] The Candidate Set remains complete, zero-based, immutable in membership and order, bounded at twenty, and equal in length to the Resume Attempt Budget.
- [ ] Progress equals the durable candidate facts for Resume Completions, Candidate Considerations, and evaluations consumed, including the pre-admission quarantine-guard exception and audited late Completion.
- [ ] Spend uses integer USD micros and always satisfies the approved committed and remaining-authorization equations without candidate-level amounts or invoice language.
- [ ] Outcome, reason, and stopping-decision time become non-null together and remain immutable; lifecycle and revision may continue through safe drain, late Completion, or trustworthy spend settlement.
- [ ] The identical all-or-nothing Resume Completion Summary appears on a completed candidate and its sealed Artifact Set evidence and is absent before the atomic seal.
- [ ] By-ID lookup returns the retained snapshot for every known run and typed `not_found` for an unknown identity without creating or mutating state.
- [ ] Active lookup returns only the queued, running, or cancelling run that holds the single scheduling claim, or a successful nullable result when no run is active.
- [ ] Latest lookup selects by immutable creation order and returns a successful nullable result when no run exists; late updates to an older run never reorder it ahead of a newer run.
- [ ] Ordinary reads use durable coordination only, perform no live workspace or PDF validation, produce no side effects, and apply `Cache-Control: no-store` to success and typed-error responses.
- [ ] Run snapshots and their bounded Candidate Sets and results have no automatic V1 pruning, while private checkpoints continue to retire under their own verified rules.
- [ ] An explicit serialization allowlist excludes source, generated content, provider detail, checkpoint material, ownership evidence, digests, paths, transient URLs, leases, attempts, and worker diagnostics.
- [ ] Fresh-application tests reopen the same durable state and reconstruct active, finished, older known, late-updated, and unknown runs without an in-memory task or cached response; the default production router and committed OpenAPI remain unchanged.

## 31. Stage idempotent Resume Run commands

**What to build:** Let an operator intentionally start and cancel one staged durable Resume Run with exact replay, readiness, conflict, empty-queue, and safe-drain behavior while the supported synchronous route remains untouched until cutover.

**Blocked by:** [Stage retained Resume Run reads](#30-stage-retained-resume-run-reads).

- [ ] Start accepts only an explicit strict integer Resume Batch Target from one through ten and a client-generated idempotency key matching the approved grammar; missing, boolean, float, numeric-string, out-of-range, `limit`, and other unknown inputs fail before mutation.
- [ ] A new key with no Active Resume Run atomically captures the fixed Candidate Set and required run facts, creates the run and permanent canonical binding, acquires the single active claim, and returns `202` with its first durable snapshot before waking execution.
- [ ] Exact key-and-target replay is resolved before active and readiness checks, returns the original run's current snapshot with `202` after any later transition, and never wakes work or acquires authority twice.
- [ ] Reusing a start key with another target returns typed `idempotency_conflict`; a distinct key during an Active Resume Run returns typed `resume_run_active` with only the active run identity, and neither request creates state.
- [ ] Start readiness returns one closed bounded Resume Run Readiness Reason plus only applicable safe configuration or workspace-schema validation failures and creates neither a run nor an idempotency binding.
- [ ] Readiness-gate selection is deterministic, distinguishes pre-start capability failure from a later authorization-blocked outcome, and exposes no raw provider, source, checkpoint, path, or evidence detail.
- [ ] Successful readiness with no eligible candidate atomically creates and binds an immediately finished zero-candidate `queue_exhausted` run with zero progress and committed exposure, the fixed ceiling, and full remaining authorization.
- [ ] The single Resume Run claim remains independent of Application Analysis, while the queue snapshot excludes Applications under active Resume Artifact Quarantine.
- [ ] Cancellation accepts no body and no idempotency key, atomically commits the forward scheduling barrier before returning, and returns `200` with the current snapshot for every known queued, running, cancelling, or finished run.
- [ ] Repeated cancellation never rewrites an earlier winning stopping decision; `200` acknowledges the command while clients continue to follow lifecycle until safe drain finishes.
- [ ] Unknown cancellation identity returns typed `not_found`, malformed cancellation requests perform no mutation, and temporary coordination loss returns sanitized `resume_coordination_unavailable` without fabricating state.
- [ ] Validation, replay, active-run, readiness, queue-snapshot, cancellation, and coordination precedence is enforced inside the command and transaction authority rather than only at the route layer.
- [ ] Deterministic public-seam matrices cover rejected-key reuse, replay before and after finish, replay of an older run while a newer one is active, every readiness reason, empty queue, cancellation races, restart after acceptance, and overlap with one Analysis Run.
- [ ] The staged routes and worker composition remain outside the default production router and committed generated client until the coordinated cutover, and the existing synchronous Resume Creation contract remains green.

## 32. Stage Artifact Set and Quarantine Worklist reads

**What to build:** Let the staged composed API inspect one retained Resume Artifact Set and independently discover every unresolved Resume Artifact Quarantine after its owning run stops, without exposing private recovery evidence or changing the supported production routes.

**Blocked by:** [Let isolated Resume Artifact Quarantine resolve without rewriting the run](#24-let-isolated-resume-artifact-quarantine-resolve-without-rewriting-the-run) and [Stage retained Resume Run reads](#30-stage-retained-resume-run-reads).

- [ ] A known Artifact Set is readable by its stable ID through the staged composition and returns one complete Resume Artifact Set Snapshot; an unknown ID returns sanitized `not_found` without mutation.
- [ ] The snapshot exposes only the approved owner and revision fields plus disposition, pending boundary, nullable quarantine, ordered available actions, nullable active action, and nullable Completion Summary.
- [ ] All four dispositions project independently of candidate state and quarantine; only `sealed` and `compensated` are terminal, use no pending boundary, and can never return to a nonterminal disposition.
- [ ] Every unsealed set reports the earliest canonical boundary not yet freshly verified; intent or dispatch alone never advances it, and relation attachment remains pending until the atomic Completion seal commits.
- [ ] The Completion Summary is non-null exactly for a sealed set, has no partial form, and is byte-for-byte identical to the owning run candidate's Completion Summary.
- [ ] A quarantine projection contains only one approved reason, episode entry time, and latest assessment time; reassessment may advance only the latter, and no history or evidence payload escapes.
- [ ] Artifact Set snapshots expose only state-derived reconciliation or compensation availability and no generic retry eligibility, retry command, acknowledgement, force completion, force cleanup, or force deletion authority.
- [ ] Revision advances for every safety-relevant Artifact Set mutation, including a hidden evidence change whose coarse public state is otherwise unchanged; identity and creation time remain fixed.
- [ ] The worklist returns only currently quarantined Artifact Sets as the same complete snapshots returned by by-ID lookup, including entries whose owning run is finished and while an unrelated Resume Run is active.
- [ ] Worklist items order by the current episode's entry time and then Artifact Set ID, use opaque cursor pagination with default twenty and range one through fifty, expose no total count, and reject malformed cursors as `invalid_cursor`.
- [ ] Resolution or replacement of an earlier quarantine episode cannot corrupt pagination, and an Artifact Set remains readable by ID after it leaves the worklist, seals, or compensates.
- [ ] A fresh application composition over the same durable state reconstructs identical Artifact Set and worklist responses without an in-memory task, cached provider response, or live external read.
- [ ] Reads perform no workspace or PDF validation and no domain mutation, are non-cacheable, and expose no source, prompt, provider, checkpoint, digest, path, raw-error, transient-URL, lease, or worker detail.
- [ ] The read operations and their named one-through-fifty pagination model remain available only in the staged composition until the atomic cutover; the existing queue pagination contract and supported route inventory remain unchanged.

## 33. Stage revision-guarded Resume Artifact Actions

**What to build:** Let an operator durably request separate Audited Resume Artifact Reconciliation or Resume Artifact Compensation through the staged API, with optimistic concurrency, exact replay, restart survival, and continuous Application mutation safety.

**Blocked by:** [Stage Artifact Set and Quarantine Worklist reads](#32-stage-artifact-set-and-quarantine-worklist-reads).

- [ ] Reconciliation and compensation remain distinct staged commands, each requiring a valid client-generated idempotency key and a body containing only a strict positive integer expected revision, and each returning `202` with the current Artifact Set Snapshot after durable acceptance.
- [ ] Invalid headers, missing or coerced revisions, nonpositive values, and extra fields return `invalid_request`, create no action or binding, and do not advance revision.
- [ ] Acceptance atomically persists a permanent binding to the Artifact Set, action kind, canonical request including expected revision, accepted revision, and acceptance time; increments Artifact Set revision; sets exactly one active action; and empties available actions before waking work.
- [ ] Exact replay resolves before every current-state check and returns `202` with the Artifact Set's current snapshot after revision advance, restart, action settlement, or a later quarantine episode without waking work twice.
- [ ] Reusing a key for another Artifact Set, action kind, expected revision, or canonical request value returns `idempotency_conflict` and performs no action.
- [ ] For a new key, an unknown set returns `not_found`; a stale revision returns `resume_artifact_state_changed`; an occupied action slot returns `resume_artifact_action_active`; and an unavailable kind returns `resume_artifact_action_unavailable`.
- [ ] Every state conflict includes the current safe Artifact Set Snapshot, advances no state, and follows the exact precedence of syntax, existing binding, resource existence, revision, active action, and availability.
- [ ] Concurrent current-revision commands serialize so at most one is accepted and every loser observes the winning revision and active action rather than dispatching another mutation.
- [ ] Reconciliation freshly assesses exact evidence and may resume only the original forward recovery or seal a proven Completion; it never deletes, compensates, adopts an independent artifact, or treats revision agreement as ownership proof.
- [ ] Compensation freshly proves exact run ownership before strict reversal, never mutates an independent artifact or sealed Completion, and cannot run when compensation is absent from available actions.
- [ ] The current quarantine and active action remain visible, preserve the Application mutation lock, and keep the set on the worklist throughout accepted assessment and resulting forward recovery or compensation; no new run can admit that Application meanwhile.
- [ ] Artifact actions neither acquire nor conflict with the single Active Resume Run claim: an action may overlap an unrelated Resume Run, and distinct quarantined Applications retain independent public command semantics.
- [ ] A fresh application instance resumes accepted intent without another HTTP command; settlement clears the active action only at seal, verified compensation, or safely re-quarantined idle state, then recomputes available actions.
- [ ] A late audited seal updates Artifact Set Completion, candidate Completion and state, run progress, and both revisions exactly once without rewriting the finished run's outcome or reason; every action response and error is sanitized and non-cacheable.
- [ ] The action operations remain confined to the staged composition until the coordinated cutover, so operator recovery is not partially exposed before its generated client and process-console controls exist.

## 34. Stage immutable Resume PDF names and verified downloads

**What to build:** Finalize one immutable human PDF name and serve a sealed Resume PDF only through its verified Artifact Set identity in the staged API, preserving historical truth when external bytes later drift.

**Blocked by:** [Commit and seal one exact Resume Artifact Set](#19-commit-and-seal-one-exact-resume-artifact-set) and [Stage Artifact Set and Quarantine Worklist reads](#32-stage-artifact-set-and-quarantine-worklist-reads).

- [ ] Company, Role, and User components are Unicode NFKC-normalized; Letters, Numbers, and Marks are preserved; every other maximal run becomes one hyphen; surrounding hyphens are removed; and case is preserved.
- [ ] Each component is truncated to at most 64 UTF-8 bytes without splitting a code point and is trimmed again if truncation exposes a trailing hyphen; the joined basename plus `.pdf` never exceeds 198 bytes.
- [ ] An empty normalized Company or Role fails at Candidate Source validity, while an empty User fails Resume Run Readiness; no placeholder is invented and no invalid Artifact Set filename is established.
- [ ] Run creation captures the valid normalized User value with the run, so later configuration changes cannot alter a candidate's naming input.
- [ ] The exact version-one basename is persisted when the Artifact Set is established and remains unchanged by later source or configuration edits and process restart.
- [ ] Equal human basenames remain distinct non-overwriting artifacts because storage, lookup, ownership, and verification use the full Artifact Set ID rather than filename.
- [ ] The staged Artifact Set download serves only a sealed set's exact indexed PDF and never falls back to Resume ID, title, basename search, legacy files, or another set's artifact.
- [ ] Before serving bytes, download verifies exact Artifact Set and index binding, configured-store path containment, expected Resume document binding, and PDF byte digest; only verified bytes receive a successful PDF response.
- [ ] A successful download uses the persisted basename in a UTF-8 content-disposition header that matches both candidate and Artifact Set Completion Summaries.
- [ ] Unknown sets and known but unsealed, unindexed, missing, path-invalid, digest-mismatched, or legacy-only PDFs all return the same sanitized `pdf_not_found` without revealing the failed check.
- [ ] Download failure after Historical Artifact Drift does not mutate the Artifact Set, reopen or compensate its sealed Completion, change run or candidate facts, or make the Application eligible again.
- [ ] A digest-verified sealed PDF referenced by a retained Completion Summary has no automatic V1 time pruning or public deletion command; verified compensation may remove only an unsealed run-owned PDF.
- [ ] A fresh application composition over the same durable state preserves the exact filename and verified download without cached response objects, transient URLs, or Resume-page identity.
- [ ] Golden tests cover punctuation and whitespace, compatibility characters, composed and decomposed Unicode, combining marks, emoji and separators, empty outputs, multibyte truncation, trailing-hyphen trimming, repeated basenames, and the exact maximum.
- [ ] Successful and failed PDF responses are non-cacheable, and public summaries and errors expose no digest, storage path, checkpoint content, private source field, or raw verification error.
- [ ] The verified download remains staged until the atomic cutover; the supported Resume-ID download route is neither removed nor used as Artifact Set authority in this ticket.

## 35. Prove the closed Resume failure taxonomy and retire the durability prototype

**What to build:** Prove every approved failure, outcome, reason, cancellation, recovery, and privacy invariant through the composed Resume Run workflow and focused contracts, then remove the throwaway durability prototype only after production coverage replaces it.

**Blocked by:** [Suspend safely through run-store and checkpoint authority loss](#28-suspend-safely-through-run-store-and-checkpoint-authority-loss), [Stage idempotent Resume Run commands](#31-stage-idempotent-resume-run-commands), [Stage revision-guarded Resume Artifact Actions](#33-stage-revision-guarded-resume-artifact-actions), and [Stage immutable Resume PDF names and verified downloads](#34-stage-immutable-resume-pdf-names-and-verified-downloads).

- [ ] Production represents Resume Run Lifecycle, Resume Run Outcome, Resume Candidate State, provider-call accounting, and Resume Artifact Set disposition as independent closed axes with exactly the values approved by the failure contract.
- [ ] Every approved semantic reason has at least one composed public Resume Run witness that proves start acceptance or rejection, failure scope, candidate disposition, run Outcome, backfill eligibility, spend disposition, artifact or quarantine disposition, and restart behavior.
- [ ] The registry rejects unknown or dynamic reasons, and all caught defects map either to their bounded semantic code, `storage_failure_unclassified` for an unclassified storage-path defect, or `run_execution_failure` for another safe Run-Scoped invariant or worker defect.
- [ ] Candidate reason presence is exact: `pending`, `evaluating`, ordinary forward `recovering`, and `completed` candidates have none; `skipped`, `failed`, `cancelled`, and `compensating` candidates have one; a recovering candidate's quarantine reason belongs to its Resume Artifact Set; Completion clears a prior candidate reason where late sealing is permitted.
- [ ] Every finished Resume Run has exactly one Outcome-compatible reason: the standard outcome reasons map exactly, cancellation uses `operator_cancelled`, and authorization-blocked and failed runs accept only reasons from their respective closed sets.
- [ ] Multi-defect acceptance cases prove first-failing-gate and within-gate precedence for all Admission fields together, source change plus an independent Resume, returned-model mismatch plus malformed output and contradictory usage, overlapping artifact invariant failures, and concurrent run-store, checkpoint, and spend defects.
- [ ] Provider matrices prove the distinction among immediate authorization or contract faults, homogeneous shared retry exhaustion, mixed `provider_recovery_exhausted`, stage-specific structured-output exhaustion, context overflow, usable output with Indeterminate billing, and proven non-transmission without exposing raw provider details.
- [ ] Workspace and artifact matrices prove the distinction among definite candidate unavailability or change, access and contract failure, incomplete versus complete-but-moving Stable Resume Source Observations, exact ownership, content, relation, and result quarantine causes, strict compensation failure, and safe unclassified fallbacks.
- [ ] The composed suite proves Candidate-Scoped backfill, Run-Scoped stop, quarantine orthogonality, immutable prior Resume Completions, fixed Resume Candidate Set exhaustion, late sealing, cancellation drain, first-stop races, and total-store suspension through the normal Resume Run boundary.
- [ ] Durable state, public snapshots, logs, events, and safe errors pass a closed allowlist and denylist audit: reasons contain no provider text, exception names, dynamic identity, source or generated content, prompts, reasoning, private checkpoints, transient URLs, or filesystem paths.
- [ ] Production contract suites retain exhaustive deterministic coverage only at the transaction and checkpoint store, prepared provider and spend, workspace, and PDF seams; broader controller, service, worker, and repository suites do not duplicate the public workflow matrix.
- [ ] All race, retry, deadline, outage, and restart cases use controlled clocks, explicit barriers, fresh application composition, deterministic provider and workspace adapters, and real production store and PDF behavior where relevant, with no sleeps, paid provider calls, or live Notion mutations.
- [ ] Every durability-prototype scenario and every Resume Source Proof and Artifact Document Digest golden vector has an equivalent passing production test before prototype-only behavior is removed.
- [ ] After production equivalence is proved, the disposable prototype, its executable entry point, package command, and documentation references are removed; the full Resume acceptance, focused contract, documentation, type, lint, generated-artifact, and behavior-inventory gates pass with no production dependency on prototype code.

## 36. Build the prototype-approved Resume process console

**What to build:** Implement the approved ticket-09 Resume Run and Resume Artifact Quarantine presentation as tested process-console components ready for final generated-client wiring.

**Blocked by:** [Prototype the durable Resume Batch dashboard](09-prototype-durable-resume-batch-dashboard.md), [Expose exact Resume Committed Spend end to end](#7-expose-exact-resume-committed-spend-end-to-end), [Prefactor dashboard durable-resource observation plumbing](#29-prefactor-dashboard-durable-resource-observation-plumbing), [Stage idempotent Resume Run commands](#31-stage-idempotent-resume-run-commands), [Stage revision-guarded Resume Artifact Actions](#33-stage-revision-guarded-resume-artifact-actions), and [Stage immutable Resume PDF names and verified downloads](#34-stage-immutable-resume-pdf-names-and-verified-downloads).

- [ ] Layout, hierarchy, wording, cadence guidance, responsive behavior, and action placement match the resolved dashboard prototype rather than introducing a second interaction design.
- [ ] The Resume Batch Target control defaults to five, permits integers from one through ten, and presents the queue as a server-owned Match Score-ordered preview rather than selected rows.
- [ ] The new console contains no per-row Create Resume action or checkbox-selection model.
- [ ] Queued, running, cancelling, and finished lifecycle are presented separately from immutable outcome and reason, including the interval where a stopping decision exists while safe drain continues.
- [ ] Primary progress distinguishes Resume Completions, Candidate Considerations, evaluations consumed, Attempt Budget, and target without deriving authoritative counters from visual row counts.
- [ ] Resume Committed Spend appears against the fixed ceiling with the shared exact USD-micro formatter, while verified cost, active reservations, indeterminate reservations, and remaining authorization remain distinct details.
- [ ] Candidate presentation uses only ordinal, immutable Application label, state, stage, bounded reason, and atomically sealed Completion links; it exposes no private source, provider, checkpoint, effect-attempt, or worker detail.
- [ ] A finished run remains visible and accepts later revisioned spend or audited Completion facts without changing its recorded outcome or appearing to be a newly created run.
- [ ] Cancellation copy states that future scheduling stops while in-flight settlement and established Artifact Set drain may continue; controls follow the prototype's queued, running, cancelling, and finished states.
- [ ] The Quarantine Worklist is visually independent of run history and supports prototype-approved pagination, stable Artifact Set inspection, available actions, active-action state, and refresh after revision conflicts.
- [ ] Reconciliation and compensation remain visibly distinct; no generic retry, acknowledgement, force-complete, force-cleanup, or force-delete control exists.
- [ ] Readiness, initial-load, polling, partial-section, action-conflict, and backend-unavailable states preserve the last safe snapshot and provide the prototype-approved recovery path.
- [ ] An independent active Analysis Run and Resume Run can be presented and controlled concurrently without either workflow disabling or overwriting the other except where its own contract requires.
- [ ] Components consume presentation models rather than handwritten API response types, have deterministic interaction and accessibility coverage, and remain unwired from production Resume commands until the atomic cutover.

## 37. Cut over the durable Resume contract atomically

**What to build:** Make durable Resume Runs and Resume Artifact Sets the sole supported Resume Creation surface across the API, generated client, dashboard, tests, and operator documentation.

**Blocked by:** [Prove the closed Resume failure taxonomy and retire the durability prototype](#35-prove-the-closed-resume-failure-taxonomy-and-retire-the-durability-prototype) and [Build the prototype-approved Resume process console](#36-build-the-prototype-approved-resume-process-console).

- [ ] The default application mounts the staged durable Resume routes and starts and stops the Resume worker through application lifespan, including fresh-process recovery of accepted runs and Artifact Set actions.
- [ ] The synchronous Resume Creation route and Resume-ID PDF route are removed in the same green integration change that enables the durable writer; no supported or deployable state exposes both Resume writers.
- [ ] Default runtime composition retires the legacy synchronous Resume mutation and its legacy effect-journal reconciliation path rather than leaving a hidden mutation authority reachable after their routes disappear.
- [ ] The supported route inventory contains the existing Resume Creation Queue plus the exact start, active, latest, by-ID, cancellation, Artifact Set, Quarantine Worklist, reconciliation, compensation, and Artifact Set PDF operations and operation IDs from ticket 08.
- [ ] OpenAPI and the generated client are regenerated from the default application; all new models and operations are exported, while every legacy `CreateResume*` and `DownloadResumePdf*` symbol is absent.
- [ ] The dashboard adapter uses only generated operations and types, sends one explicit target and caller-owned key per intentional start, follows typed active-run conflict, and never automatically retries a failed command.
- [ ] Dashboard startup reconnects independently to an Active Resume Run, rediscovers the Latest Resume Run when appropriate, loads unresolved quarantines, and continues to support a simultaneous Analysis Run.
- [ ] The production dashboard switches to the prototype-approved process console, removes per-row Resume creation state and transient response-memory results, and retains sealed Resume, Note, and Artifact Set PDF links through durable snapshots.
- [ ] Reconciliation and compensation send one caller-owned idempotency key plus the observed expected revision, follow the stable Artifact Set identity after `202`, and refresh from the current snapshot on every typed state conflict.
- [ ] Dynamic Resume JSON, typed errors, and verified PDF responses are non-cacheable; request-body media-type enforcement covers parameterized action routes while bodyless cancellation remains valid.
- [ ] Artifact Set PDF links use the persisted UTF-8 basename and fail closed for unknown, unsealed, missing, modified, or legacy-only files; removed legacy routes return ordinary `404` and perform no workspace, PDF, or durable-state mutation.
- [ ] Public errors expose only approved bounded codes and safe sibling fields, including readiness reason, active run identity, and current Artifact Set; no raw provider, source, checkpoint, path, or evidence detail escapes.
- [ ] Contract tests lock exact routes, operation IDs, statuses, strict request bounds, closed enums, response models, conflict precedence, non-cacheable semantics, and equality between emitted and committed OpenAPI.
- [ ] Fresh-application acceptance tests cover start, replay, reconnect, cancel, zero-candidate completion, simultaneous Analysis execution, quarantine discovery, restart during each action, late Completion, post-finish spend revision, verified PDF download, and legacy-route non-mutation.
- [ ] Legacy synchronous-route tests and behavior inventory entries migrate to the durable public seam, operator and architecture documentation describe only the supported contract, and the complete generated, type, lint, test, build, privacy, and final gates pass.
