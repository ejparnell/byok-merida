# Set the Resume Run Spend Ceiling

Parent: [Wayfinder: Durable Batched Resume Creation](map.md)

Type: grilling

Status: ready-for-agent

State: closed

Assignee: codex

Blocked by: [Prove conservative Resume Generation cost bounds](02-prove-conservative-resume-generation-cost-bounds.md)

## Question

What fixed dollar ceiling should one operator-started Resume Run enforce, given the conservative and expected cost evidence for targets 1 through 10, and what pre-dispatch authorization, reservation, settlement, readiness, and operator-visible Committed Spend rules preserve the approved Resume Generation Envelope without allowing uncertainty or recovery to oversubscribe that ceiling?

## Decisions

- Every Resume Run has a fixed Resume Run Spend Ceiling of exactly 1,000,000 USD micros ($1.00), independent of its Resume Batch Target.
- The ceiling is a hard authorization-ledger bound under the currently approved prices: Merida never authorizes Resume Call Reservations whose Resume Committed Spend would exceed it. Provider adherence to those prices is an explicit external billing assumption, so the ceiling is not represented as an unconditional cap on an incorrect provider invoice.
- The ceiling makes target completion best-effort. When the next full Resume Call Reservation cannot fit, the run stops with a spend-limited outcome rather than overspending, changing the Resume Generation Envelope, or rolling back earlier Resume Completions.
- The checked-in two-role fixture projects a conservative four-call reservation of 35,712 USD micros per candidate and 714,240 USD micros for the maximum 20-candidate set. This is fixture evidence, not an expected production-cost distribution. The context-limit extrema remain 1,166,160 USD micros per candidate and 23,323,200 USD micros for 20 candidates.
- Resume Cost Authorization occurs call by call immediately before every provider transmission. The exact next request is rendered once, its complete worst-case Resume Call Reservation is atomically and durably held against the remaining ceiling, and only those exact bytes may then be dispatched.
- A Resume Run does not reserve an entire candidate upfront because the exact Draft request does not exist until Fit Requirement extraction and evidence selection finish. A paid Requirements call may therefore be followed by a spend-limited stop when the Draft reservation cannot fit; that candidate produces no Resume Completion and its earlier provider spend remains committed.
- Resume Cost Settlement releases an entire reservation only after proven pre-transmission failure. It settles downward only from a trustworthy matching receipt whose request identity, exact model, token totals, cache accounting, reasoning-inclusive output usage, and reservation bounds reconcile; valid billing evidence may settle a call even when its generated output is unusable.
- A sent or possibly sent call with missing, malformed, mismatched, or out-of-bound evidence becomes an Indeterminate Resume Call and keeps its complete reservation committed. Every recovery consumes a separate dispatch slot and requires a fresh Resume Cost Authorization.
- Resume Spend Readiness fails closed before run creation unless both approved stages are ready: exact Flash/8K and Pro/16K endpoint/model rate-card entries with pricing evidence no older than 30 days; verified pinned tokenizer artifacts and independently derived protocol overhead; render-once/send-exactly-once transport with safe usage-evidence capture; successful sanitized acceptance probes for both envelopes; and an available transactional reservation store.
- Time-sensitive approval and reservation-authority checks repeat before every call and after restart. A failed check prevents another provider transmission; the later failure-policy ticket owns the terminal outcome and reason-code vocabulary.
- Resume Committed Spend is exactly verified provider cost plus active reservations plus indeterminate reservations. The primary operator view compares it with the $1.00 ceiling, while expanded detail separates those three constituents and the remaining authorized budget; it is never labeled actual cost.
- All authoritative monetary accounting and reconciliation use integer USD micros. Dollar strings are presentation values only and never participate in authorization or settlement.
- Operator-facing spend values render exactly with up to six decimal places, trimming trailing zeros while retaining at least two digits. Nonzero micro-dollar values never round to `$0.00`; the primary line and expanded breakdown use the same exact formatter.
- For each exact rendered call, the Resume Input Cost Bound is `max(pinned-tokenizer token count, complete UTF-8 body byte count) + reviewed stage protocol overhead`. The call is rejected before transmission when that bound plus its stage output allowance exceeds the approved one-million-token context.
- Resume Call Reservations price the Resume Input Cost Bound at the approved cache-miss input rate and the complete reasoning-inclusive 8,000-token Requirements or 16,000-token Draft allowance at the approved output rate. Each component rounds upward in integer USD micros; cache-hit savings apply only during trustworthy settlement.
- Character ratios, fixture averages, runtime price scraping, projected whole-candidate estimates, and assumed cache hits cannot authorize a call.
- Merida's backend is the Resume Spend Enforcement Authority. Its Resume-owned transactional run ledger decides whether each call may dispatch; DeepSeek account balance and account-wide gateway controls cannot isolate one Resume Run or an overlapping Analysis Run.
- Provider or gateway unit-price and spending controls are defense in depth when available. Their absence does not block Resume Spend Readiness when the local authority is ready; contradictory provider price or usage evidence prevents further transmission, retains the authorized reservation, and surfaces a provider-pricing anomaly without claiming that Merida bounded the provider's incorrect invoice. The later failure-policy ticket owns the terminal outcome and reason code.
- Resume Call Reservations never expire automatically. After restart, only a durable state that proves dispatch never began may release a pre-dispatch reservation; a crash, timeout, cancelled task, expired worker lease, missing response, or elapsed time is not proof.
- Once dispatch may have begun, recovery must obtain trustworthy matching usage evidence or convert the complete reservation to an Indeterminate Resume Call. Recovery and cancellation never restore its dispatch slot merely because no response was observed.
- The 1,000,000-micro ceiling is a fixed, versioned policy captured durably by every Resume Run. It does not scale with target and has no request-level or operator override.
- Provider price changes alter only newly authorized Resume Call Reservations, not the run ceiling. Each existing reservation retains its authorization fingerprint and rates; later calls use the currently approved rate card. A reviewed policy change to the ceiling or Resume Generation Envelope applies only to new runs, while existing runs retain their captured ceiling.
- A reservation equal to the remaining authorized budget is admitted; a reservation even one micro greater is denied. Atomic admission keeps Resume Committed Spend at or below the captured ceiling under every local concurrency, recovery, and cancellation path.

## Fixture Projection Evidence

The risk-policy anchor is reproducible from `apps/api/tests/test_deepseek_resume.py`, specifically `test_resume_graph_preserves_distinct_roles_with_the_same_heading`, `analyzed_application("Own reliable Python services and API delivery.")`, and `master_resume_with_duplicate_role_headings()`. The checked-in requirement fixture contains one supported Backend requirement, and the derived Draft input contains two role targets and ten evidence items.

Messages use the current `_requirement_messages`, `_resume_messages`, and `JsonPromptPayloadEncoder` paths. The projection serializes the accepted planned wire fields in compact UTF-8 JSON using the existing prepared Analysis renderer's field and role mapping. Counts use the pinned DeepSeek V4 tokenizer, the researched rates and output allowances, and provisional protocol overhead `H = 27`; byte counts dominate token counts in all four requests:

| Call | UTF-8 bytes | Tokenizer tokens | Input Cost Bound | Reservation |
| --- | ---: | ---: | ---: | ---: |
| Requirements initial | 1,145 | 291 | 1,172 | 2,405 micros |
| Requirements repair (`unsupported_requirement_evidence`) | 1,292 | 322 | 1,319 | 2,425 micros |
| Draft initial | 3,399 | 915 | 3,426 | 15,411 micros |
| Draft repair (`unsupported_requirement`) | 3,537 | 944 | 3,564 | 15,471 micros |

One initial call per stage reserves 17,816 micros. All four stage slots reserve 35,712 micros per candidate, or 714,240 micros for 20 identical candidates. This is deterministic fixture evidence used to select a risk-tolerance policy, not a representative production distribution or authorization authority. Production remains fail-closed until exact Resume render-once/send-once transport and approved Flash/Pro Resume rate-card entries independently verify the protocol overhead and all other readiness evidence.

## Answer

Every Resume Run captures a fixed Resume Run Spend Ceiling of 1,000,000 USD micros ($1.00), independent of its Resume Batch Target and without an operator override. It is a hard authorization-ledger ceiling under approved prices: Merida never permits Resume Committed Spend to exceed the captured amount, while provider adherence to those approved prices remains an explicit external billing assumption.

Resume Cost Authorization occurs immediately before each call. Merida renders the exact request once, proves its context fit, computes its complete Resume Call Reservation from conservative input and reasoning-inclusive output bounds, atomically reserves that amount, and transmits only the reserved bytes. The exact-boundary reservation is permitted; one micro beyond the remaining authorized budget is not. Because a Draft request does not exist before Requirements and evidence selection complete, there is no whole-candidate reservation. A run may spend on Requirements and then finish as a Spend-Limited Resume Run if its Draft cannot fit.

Resume Cost Settlement releases value only after proven non-transmission or trustworthy matching usage evidence. Uncertainty never expires: an ambiguous sent call retains its full reservation as an Indeterminate Resume Call across timeout, cancellation, lease expiry, and restart. Every recovery consumes its stage slot and requires a fresh authorization.

Resume Spend Readiness requires both exact stage approvals, current pricing, pinned tokenizer and reviewed protocol evidence, prepared render-once/send-exactly-once transport, safe response evidence, sanitized acceptance probes, and transactional reservation authority. These time-sensitive controls are rechecked before later calls and after restart. Provider pricing anomalies block further calls but do not create a false claim that Merida can cap an incorrect external invoice.

Operators see exact Resume Committed Spend—verified provider cost plus active and indeterminate reservations—against `$1.00`, with all components and remaining authorized budget available separately. Values are kept in integer USD micros and displayed with up to six decimal places so nonzero spend never appears as `$0.00`.

## Problem Statement

Batched Resume Creation can pursue up to ten Resume Completions from a Resume Candidate Set containing as many as twenty Applications. Each candidate may use two Requirements calls and two Draft calls, and the two stages have different models, output allowances, and prices. Retries, repairs, timeouts, crashes, and ambiguous transmissions make actual billing impossible to predict safely before a run.

Without a fixed authorization ceiling and durable call-level accounting, batching could silently multiply provider spend, optimistically refund uncertain calls, or lower generation quality to keep going. A typical prompt estimate is not sufficient because accepted input sizes can approach the model context, and a maximum-context candidate alone can require more than one dollar of reservations. The operator needs a predictable local authorization boundary while accepting that a Resume Batch Target is best-effort under that boundary.

## Solution

Give every Resume Run a fixed, versioned `$1.00` Resume Run Spend Ceiling under approved provider prices. Before each provider transmission, Merida renders the exact call once and durably reserves its complete conservative worst-case charge. A call is dispatched only when that reservation fits atomically within the remaining ceiling. Requirements and Draft retain their approved Resume Generation Envelope; spend pressure never changes models, thinking effort, output bounds, or recovery behavior.

Trustworthy usage evidence settles a reservation downward, while proven non-transmission releases it completely. Missing or contradictory evidence remains conservatively committed. When the next complete reservation cannot fit, the run preserves its Resume Completions and finishes as a Spend-Limited Resume Run. The operator sees exact Resume Committed Spend and its verified, active, indeterminate, and remaining components without those values being mislabeled as the provider's final invoice.

## User Stories

1. As an operator, I want every Resume Run limited to one dollar of locally authorized provider spend, so that batching has a predictable risk boundary.
2. As an operator, I want the same ceiling for every Resume Batch Target, so that choosing a larger target does not silently increase my maximum authorization.
3. As an operator, I want no per-run ceiling override, so that an accidental request cannot bypass the reviewed policy.
4. As an operator, I want target completion to be best-effort under the ceiling, so that cost safety takes precedence over completing every requested Resume.
5. As an operator, I want completed Resumes preserved when spend runs out, so that useful work is not rolled back.
6. As an operator, I want a Spend-Limited Resume Run reported as a valid partial outcome, so that I can distinguish it from a total workflow failure.
7. As an operator, I want spend pressure never to change the Resume Generation Envelope, so that cost control does not silently reduce Resume quality.
8. As an operator, I want every initial call, repair, retry, and ambiguous call charged against the same ceiling, so that recovery cannot bypass the limit.
9. As an operator, I want Merida to authorize the exact next request rather than a typical prompt estimate, so that unusually large Applications are handled safely.
10. As an operator, I want a call withheld before transmission when its complete reservation cannot fit, so that the local ledger never oversubscribes the ceiling.
11. As an operator, I want a reservation equal to the exact remaining budget admitted, so that the full approved ceiling remains usable.
12. As an operator, I want a reservation one micro above the remaining budget denied, so that rounding cannot weaken the boundary.
13. As an operator, I want reservations recorded atomically before dispatch, so that concurrent activity and crashes cannot authorize the same remaining money twice.
14. As an operator, I want Merida to send exactly the request bytes it measured, so that authorization evidence matches the provider call.
15. As an operator, I want authorization performed call by call, so that Merida does not pretend to know a Draft request before Requirements and evidence selection finish.
16. As an operator, I accept that a paid Requirements call may not lead to a Resume Completion, so that Merida does not overspend merely to finish a partially processed candidate.
17. As an operator, I want each recovery to require a new call slot and reservation, so that an earlier ambiguous call is never treated as free.
18. As an operator, I want cache-miss pricing used for authorization, so that expected cache savings cannot weaken the ceiling.
19. As an operator, I want cache-hit savings recognized only after trustworthy settlement, so that genuine savings can fund later authorized calls safely.
20. As an operator, I want the complete reasoning-inclusive output allowance reserved, so that hidden thinking tokens do not create unaccounted exposure.
21. As an operator, I want an over-context request rejected before transmission, so that Merida does not pay for a request outside the approved envelope.
22. As an operator, I want source content left intact rather than silently truncated for affordability, so that cost control does not alter evidence quality.
23. As an operator, I want character ratios and fixture averages excluded from authorization, so that estimates cannot masquerade as hard bounds.
24. As an operator, I want all authoritative amounts represented in integer USD micros, so that floating-point rounding cannot oversubscribe the ceiling.
25. As an operator, I want a proven pre-transmission failure to release its reservation, so that money known not to be at risk remains available.
26. As an operator, I want a valid usage receipt to release only the proven unused portion, so that settlement remains conservative.
27. As an operator, I want billing evidence judged separately from generated-output validity, so that an unusable response can still be settled honestly.
28. As an operator, I want a sent call with missing or mismatched usage to retain its full reservation, so that uncertainty is visible rather than optimistically refunded.
29. As an operator, I want reservations never to expire merely with time, so that a timeout or stale worker lease cannot manufacture budget.
30. As an operator, I want restart recovery to preserve ambiguous reservations and consumed call slots, so that a process crash cannot duplicate paid work.
31. As an operator, I want cancellation to preserve the reservation for any possibly sent call, so that stopping a run does not imply a refund Merida cannot prove.
32. As an operator, I want Resume Spend Readiness to validate both Requirements and Draft before a run starts, so that Merida does not pay for extraction when drafting was never authorized.
33. As an operator, I want both exact endpoint and model combinations reviewed, so that a configured but unapproved model cannot receive paid work.
34. As an operator, I want pricing approval refreshed at least every thirty days, so that stale rates cannot remain authorization authority indefinitely.
35. As an operator, I want pinned tokenizer and reviewed protocol evidence for both stages, so that input bounds are reproducible and fail closed.
36. As an operator, I want sanitized provider probes for both stage envelopes, so that readiness reflects real provider behavior without persisting private content.
37. As an operator, I want transactional reservation authority checked before work begins, so that calls cannot run when the spend ledger is unavailable.
38. As an operator, I want time-sensitive readiness rechecked before later calls and after restart, so that a run cannot continue under expired authority.
39. As an operator, I want contradictory pricing or usage evidence to stop further calls, so that a suspected provider-pricing anomaly cannot compound.
40. As an operator, I want provider and gateway controls treated as additional protection, so that account-wide tools do not replace run-specific enforcement.
41. As an operator, I want an overlapping Application Analysis Run to retain its separate ceiling, so that account-level controls do not conflate the two workflows.
42. As an operator, I want Resume Committed Spend shown against `$1.00`, so that I can understand current conservative exposure at a glance.
43. As an operator, I want verified cost, active reservations, indeterminate reservations, and remaining authorized budget shown separately, so that I can understand why money remains committed.
44. As an operator, I want Committed Spend distinguished from actual cost, so that uncertain exposure is not presented as a provider invoice.
45. As an operator, I want nonzero micro-dollar values shown precisely, so that a small Requirements reservation never appears as `$0.00`.
46. As an operator, I want each run to retain its captured policy version and ceiling, so that a later configuration change cannot rewrite an active run's contract.
47. As an operator, I want provider price updates applied to newly authorized calls, so that later dispatches use current approval without changing earlier reservation evidence.
48. As an operator, I want an existing reservation to retain its approval fingerprint and rates, so that its authorization remains auditable after a rate-card update.
49. As an operator, I want a reviewed ceiling or envelope change to apply only to new runs, so that in-progress and recovered runs remain deterministic.
50. As a maintainer, I want authorization records to retain safe fingerprints and numeric evidence without prompts or Resume content, so that spend decisions are auditable without duplicating private data.
51. As a maintainer, I want deterministic fixture projections labeled as calibration evidence rather than expected production cost, so that policy rationale remains honest about its uncertainty.
52. As a maintainer, I want provider adherence to approved prices documented as an external assumption, so that Merida does not promise control over an incorrect external invoice.

## Implementation Decisions

- The Resume Run Spend Ceiling is exactly 1,000,000 USD micros for every run and is independent of the Resume Batch Target.
- The ceiling is the maximum Resume Committed Spend Merida may authorize under approved prices. Provider adherence to those prices is an external billing assumption; the product does not claim to cap an incorrect provider invoice.
- Every run durably captures the ceiling and spend-policy version used at creation. There is no request field, environment override, target multiplier, or operator control that changes the ceiling for one run.
- A reviewed future ceiling or Resume Generation Envelope change applies only to newly created runs. Existing runs retain their captured ceiling, while each new call still requires current model and pricing approval.
- Merida's backend is the Resume Spend Enforcement Authority. The Resumes context owns the transactional run ledger and spend invariants. Account-level provider or gateway controls are defense in depth and do not replace run-specific authorization.
- Resume Cost Authorization occurs immediately before every provider transmission. It renders the request once, validates the approved endpoint, model, protocol, output allowance, and context, computes the Resume Call Reservation, persists that reservation atomically, and then transmits only those exact bytes.
- The Resume Input Cost Bound is the greater of the complete rendered UTF-8 byte count and the pinned-tokenizer count of the same request, plus independently reviewed protocol overhead for that exact stage envelope.
- The Requirements reservation uses approved cache-miss input pricing plus the complete 8,000-token reasoning-inclusive output allowance. The Draft reservation uses approved cache-miss input pricing plus the complete 16,000-token reasoning-inclusive output allowance. Input and output components each use upward integer-micro rounding.
- The input bound plus the stage output allowance must fit within the approved one-million-token context before reservation. An over-context call is not transmitted, and source content is not silently truncated or summarized to obtain authorization.
- Character ratios, expected cache hits, fixture averages, projected whole-candidate prices, and runtime page scraping are not authorization authorities.
- Reservation admission is serialized and transactional. A reservation equal to the remaining authorized budget succeeds, one micro more fails, and Resume Committed Spend never exceeds the run's captured ceiling under local execution.
- Authorization is call-level rather than candidate-level because the exact Draft request is derived only after Requirements and evidence selection. Spending on Requirements does not obligate Merida to authorize Draft.
- If the next reservation cannot fit, no provider transmission occurs. The run preserves earlier Resume Completions and stops as a Spend-Limited Resume Run without changing models, thinking effort, output allowances, or recovery rules.
- Every initial generation, transient recovery, truncation recovery, JSON repair, and semantic repair consumes the accepted stage dispatch budget and requires a separate Resume Cost Authorization. No nested transport retry or restored slot exists.
- A durable pre-dispatch state may release the complete reservation only when it proves transmission did not begin. A reservation never expires based on elapsed time, timeout, cancellation, worker lease expiry, or missing response.
- Resume Cost Settlement converts a reservation to verified provider cost only from trustworthy matching evidence. The receipt must reconcile completion identity, returned exact model, finish reason, prompt and completion totals, cache-hit and cache-miss input, reasoning-inclusive output, and reservation bounds.
- Output usability and billing settlement are independent. A malformed, truncated, filtered, or semantically invalid response may still have trustworthy usage that settles its reservation before recovery.
- A sent or possibly sent call with missing, malformed, mismatched, contradictory, or out-of-bound evidence becomes an Indeterminate Resume Call. Its complete reservation remains committed and any recovery requires another stage slot and reservation.
- Resume Committed Spend is exactly verified provider cost plus active reservations plus indeterminate reservations. Remaining authorized budget is the captured ceiling less Resume Committed Spend.
- Authoritative amounts are stored and reconciled as integer USD micros. Operator-facing values use one exact formatter with up to six decimal places, trim trailing zeros, retain at least two decimal digits, and never round a nonzero value to `$0.00`.
- The primary operator spend presentation is Resume Committed Spend against `$1.00`. Expanded detail exposes verified provider cost, active reservations, indeterminate reservations, and remaining authorized budget, and never labels Resume Committed Spend as actual cost.
- Resume Spend Readiness requires current separate approvals for Flash/8K Requirements and Pro/16K Draft at the exact endpoint. Each approval records authoritative price evidence, a validity window no longer than thirty days, pinned tokenizer provenance, independently derived protocol overhead, context and output bounds, and an approval fingerprint.
- Resume Spend Readiness also requires render-once/send-exactly-once transport, safe receipt capture, sanitized acceptance probes for both stage envelopes, and an available transactional reservation ledger. Missing, stale, or mismatched evidence fails closed.
- Time-sensitive approval and spend-authority checks run before run creation, immediately before each call, and during restart recovery before any new transmission.
- Existing reservations retain the approval fingerprint and rates used when authorized. Later calls use the currently approved rate card without rewriting prior authorization evidence.
- Contradictory provider price or usage evidence stops further transmissions and retains the authorized reservation while surfacing a provider-pricing anomaly. The later failure-policy work owns its terminal outcome and stable reason code.
- The generic estimation, approval, tokenizer, integer-micro, and settlement mechanics may be extracted from the proven Application Analysis spend kernel. Resume rate cards, ledger records, policy constants, stage identities, outcomes, and transaction ownership remain Resumes-owned.
- Durable spend records contain coordination metadata, request and approval fingerprints, bounded numeric evidence, safe provider identities, and reservation states. They do not persist prompts, Job Content, Master Resume content, generated Resume text, or model reasoning.
- The `$1.00` policy is supported by deterministic checked-in fixture calibration, not a claim about expected production cost. At the accepted provisional overhead, the largest checked-in two-role fixture reserves 35,712 micros across all four calls and 714,240 micros across twenty identical candidates; production authorization remains based only on exact requests and approved evidence.

## Testing Decisions

- Tests assert externally observable authorization, transmission, settlement, restart, readiness, and presentation behavior rather than private helper names, database table names, or incidental worker timing.
- The primary acceptance seam is the eventual public Resume Run API through the normal FastAPI composition, using the real Resumes-owned transactional run store and deterministic workspace, provider, clock, rate-card, tokenizer, and transmission barriers. This seam should prove that run-level Resume Committed Spend never exceeds 1,000,000 micros while candidates, recovery, cancellation, and restart progress normally.
- The public seam should prove a target-met run, a Spend-Limited Resume Run before any call, and a candidate that spends on Requirements before Draft is denied. Each case must preserve earlier Resume Completions and show reconciled spend components.
- A focused prepared-provider seam verifies that the exact rendered bytes used for estimation are the bytes transmitted and that Requirements and Draft retain their exact model, thinking, effort, JSON, streaming, output, and timeout envelope.
- The prepared-provider seam verifies capture of completion identity, returned model, finish reason, prompt and completion usage, cache split, reasoning usage, and transmission state while proving that prompts, private source content, generated content, and reasoning are omitted from durable spend metadata.
- A focused pure spend-policy seam verifies each approved stage's tokenizer and UTF-8 branches, protocol overhead, context boundary, cache-miss reservation arithmetic, upward integer rounding, approval expiry, endpoint/model/output mismatch, and fail-closed behavior when evidence is missing.
- Pure policy tests cover an exact reservation boundary, denial one micro over, output-inclusive context overflow, non-ASCII request bytes, tokenizer artifact mismatch, provisional or missing protocol approval, and stale pricing evidence.
- Settlement tests cover valid cache-hit and cache-miss receipts, reasoning-inclusive completion totals, valid usage paired with unusable output, proven non-transmission, missing request identity, returned-model mismatch, malformed totals, usage beyond the reservation, and provider-pricing anomalies.
- One narrow transactional-ledger contract test may inspect durable reservation behavior to prove atomic no-oversubscription under concurrent authorization attempts. All broader behavior remains at the public API seam.
- Restart tests create a fresh application instance over the same durable run state. They prove that pre-dispatch reservations release only from affirmative non-transmission evidence, while dispatching or sent reservations become or remain indeterminate and never regain their call slots automatically.
- Cancellation tests use controlled provider barriers rather than sleeps. They prove that cancellation prevents new calls without refunding an in-flight or ambiguous call and that trustworthy in-flight usage may still settle.
- Readiness tests prove that either missing stage approval, expired pricing, tokenizer or protocol mismatch, failed sanitized probe contract, unavailable exact transport, or unavailable reservation authority blocks run creation before provider spend.
- Recovery tests prove that every post-restart call is reauthorized using the current approved rate card and remaining ceiling while prior reservations retain their original approval evidence.
- Presentation tests prove the primary `$x / $1.00` value, the four-part breakdown, the prohibition on the label `actual cost`, and exact formatting for values such as `$0.002405`, `$0.71424`, and `$1.00`.
- A deterministic calibration test may reproduce the documented two-role fixture projection. Its name and assertions must identify it as fixture evidence rather than production expected cost, and it cannot replace exact runtime authorization tests.
- Sanitized recorded-provider acceptance probes are operational readiness evidence, not routine paid test-suite calls. Normal automated tests use deterministic recordings or adapters and never make paid provider transmissions.
- Application Analysis authorization, run-store, restart, public-API, and dashboard spend tests are prior art for the seams and invariants. Resume tests should reuse their behavioral shape without importing Analysis-owned policy constants, outcome names, or persistence schema.

## Out of Scope

- Choosing or changing the accepted Flash/8K Requirements and Pro/16K Draft Resume Generation Envelope.
- Guaranteeing that every Resume Batch Target completes under `$1.00` or sizing the ceiling to the theoretical maximum-context Candidate Set.
- Predicting a representative production cost distribution from the current fixture corpus.
- Enforcing or correcting an external provider invoice when the provider violates approved pricing.
- Defining the complete Resume Run lifecycle, failure precedence, stable reason-code vocabulary, or cancellation outcome taxonomy beyond the spend invariants required here.
- Selecting the durable store schema, lease algorithm, worker cadence, or generic durable-run abstraction.
- Defining source consistency, candidate revalidation, or Master Resume snapshot behavior.
- Defining run-owned artifact identity, Notion/PDF effect ordering, partial-artifact recovery, or historical repair.
- Defining public route names, operation IDs, complete run response schemas, polling cadence, or terminal-result retention.
- Designing the full Resume Batch dashboard beyond its spend values and exact monetary formatting contract.
- Adding a model fallback, nested transport retry, automatic quality reduction, dynamic target-based ceiling, per-run override, or provider-price scraping.
- Changing Application Analysis behavior, its `$0.50` ceiling, its public contract, or its Applications-owned ledger.
- Preventing a separately authorized Application Analysis Run from overlapping one Resume Run.

## Further Notes

- The source research is [Conservative Resume Generation Cost Bounds](research-conservative-resume-generation-cost-bounds.md) and [Research: Two-stage Resume Generation Envelope](research-two-stage-resume-generation-envelope.md).
- The fixture projection is deliberately smaller than the context-bound extrema. One maximum-context candidate may require 1,166,160 micros across four calls, while twenty may expose 23,323,200 micros. The selected `$1.00` ceiling is therefore a conscious best-effort risk policy, not a completion guarantee.
- The repository does not yet contain a representative production Resume cost corpus. Future observations may motivate a reviewed policy change, but they cannot weaken exact per-call authorization or silently rewrite existing runs.
- The researched 27-token protocol overhead is an evidence-backed candidate, not yet approved for Resume/Pro. Resume Spend Readiness remains blocked until both stage entries contain independently reviewed evidence.
- No ADR is added for the dollar amount because it is an explicit, versioned, reversible product policy. The durable ownership and enforcement approach follows the established context boundary rather than introducing a new architectural choice.
