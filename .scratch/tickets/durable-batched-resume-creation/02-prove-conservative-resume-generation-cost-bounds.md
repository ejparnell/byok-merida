# Prove conservative Resume Generation cost bounds

Parent: [Wayfinder: Durable Batched Resume Creation](map.md)

Type: research

Status: ready-for-agent

State: closed

Assignee: codex

Blocked by: [Establish the two-stage Resume Generation Envelope](01-establish-two-stage-resume-generation-envelope.md)

## Question

For the accepted two-stage Resume Generation Envelope, what complete worst-case USD-micro reservation can Merida prove for every permitted transmission using current authoritative cache-miss input and reasoning-inclusive output prices, exact rendered requests, approved tokenizer plus UTF-8/protocol bounds, model context limits, and trustworthy settlement evidence?

The resolution should cover every approved model and fallback, quantify conservative per-stage and per-candidate ranges, project targets 1 through 10 with Candidate Sets up to twice the target, identify which missing or ambiguous evidence remains fully committed, assess reuse of the Analysis rate-card and authorization abstractions, and link a Markdown research asset.

## Answer

The formulas, source audit, tokenizer evidence, and full projection are recorded in [Conservative Resume Generation Cost Bounds](research-conservative-resume-generation-cost-bounds.md).

For each call `c`, calculate its Input Cost Bound as:

```text
I_c = max(complete rendered request UTF-8 bytes,
          revision-pinned tokenizer count of that same request)
      + reviewed stage protocol overhead
```

Require `I_c + O_c <= 1,000,000`, then reserve with integer ceiling rounding at the current authoritative cache-miss and reasoning-inclusive output prices:

```text
Flash Requirements(c) = ceil(I_c × 140,000 / 1,000,000) + 2,240 micros
Pro Draft(c)           = ceil(I_c × 435,000 / 1,000,000) + 13,920 micros
```

The fixed output portions are 8,000 × 280,000 micros per million for Requirements and 16,000 × 870,000 micros per million for Drafts. A candidate's complete reservation bound is the sum of up to two independently rendered Flash Requirements calls and two independently rendered Pro Draft calls. There is no fallback branch in the accepted envelope.

Because Job Content and selected Master Resume evidence have no smaller global source-size limit, authorization must use each exact rendered request; a typical-size constant cannot prove a hard bound. At the model-context boundary, one Flash call reserves at most 141,120 micros, one Pro call at most 441,960 micros, and all four calls for one candidate reserve at most 1,166,160 micros ($1.166160). The resulting safe planning extrema are:

| Resume Batch Target | Maximum candidates | Context-bound exposure |
| ---: | ---: | ---: |
| 1 | 2 | $2.332320 |
| 2 | 4 | $4.664640 |
| 3 | 6 | $6.996960 |
| 4 | 8 | $9.329280 |
| 5 | 10 | $11.661600 |
| 6 | 12 | $13.993920 |
| 7 | 14 | $16.326240 |
| 8 | 16 | $18.658560 |
| 9 | 18 | $20.990880 |
| 10 | 20 | $23.323200 |

These figures are safe extrema, not expected prices or the chosen Resume Run Spend Ceiling. The dependent [Set the Resume Run Spend Ceiling](03-set-resume-run-spend-ceiling.md) decision must compare representative exact-render costs with these extrema and may intentionally stop a run as spend-limited before its full Candidate Set is attempted.

Reuse the Analysis cost machinery only after extracting a provider-spend kernel: reviewed exact endpoint/model rate-card entries, short approval validity, pinned tokenizer and protocol hashes, exact request fingerprints, greater-of tokenizer/UTF-8 bounds, integer-micro arithmetic, context admission, reserve-before-send, evidence validation, and conservative settlement. Keep the Resumes ledger and policy constants Resume-owned; do not reuse the Analysis-only Flash/8K approval, $0.50 ceiling, hard-coded field names, outcomes, or tables.

Only a matching completion ID, returned model, finish reason, and internally reconciling usage may settle a reservation downward. A proven pre-transmission failure releases it; a sent call with missing, malformed, mismatched, or unreconcilable evidence retains its entire reservation as committed and any recovery needs a fresh slot and reservation.

Two readiness gaps remain fail-closed implementation prerequisites: Resume-specific reviewed approvals for Flash/8K and Pro/16K, and an explicit derivation of each stage's largest three-message protocol overhead. The official Pro tokenizer and encoder hashes match the pinned Flash sources, making 27 tokens the evidence-backed candidate overhead, but it is not approved for Resume/Pro until reviewed. The legacy opaque Resume transport cannot authorize or settle calls and must be replaced by render-once/send-exactly-once behavior.
