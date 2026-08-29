# Conservative Resume Generation Cost Bounds

Research date: 2026-08-13

## Conclusion

Merida can prove a hard provider-spend bound for the proposed Resume Generation Envelope, but it cannot name one context-independent dollar amount per Resume: each input reservation must be calculated from that call's exact rendered UTF-8 request. The accepted envelope has at most four dispatches and four possible transmissions per candidate:

| Stage | Exact model | Output cap | Dispatch/transmission slots | Cache-miss input rate | Reasoning-inclusive output rate |
| --- | --- | ---: | ---: | ---: | ---: |
| Fit Requirement extraction | `deepseek-v4-flash` | 8,000 tokens | 2 | 140,000 USD micros / 1M tokens | 280,000 USD micros / 1M tokens |
| Resume Draft | `deepseek-v4-pro` | 16,000 tokens | 2 | 435,000 USD micros / 1M tokens | 870,000 USD micros / 1M tokens |

The rates are the provider's current cache-miss and output prices: $0.14/$0.28 per million tokens for Flash and $0.435/$0.87 for Pro. DeepSeek says billing is input tokens plus output tokens; the output quantity includes thinking tokens through `completion_tokens`, with `reasoning_tokens` supplied as a breakdown. Both models have a 1,000,000-token context and a provider maximum output of 384,000 tokens, so Merida's 8,000/16,000 limits are stricter product bounds. [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/) [DeepSeek Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion) [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)

No fallback model belongs in v1. The current Flash-primary then Pro-on-provider-error draft path is therefore excluded from accepted arithmetic; it is documented below only as an unsafe baseline.

## Exact authorization arithmetic

For transmitted call `c`, let:

- `B_c` be the length in bytes of the **complete canonical JSON HTTP body** sent to `https://api.deepseek.com/v1/chat/completions`, after rendering every prompt byte and all protocol fields;
- `T_c` be the token count of that same canonical JSON body under the revision-pinned tokenizer approved for the exact model;
- `H_s` be the reviewed chat-protocol overhead for stage `s` and its largest permitted three-message repair form;
- `I_c = max(B_c, T_c) + H_s`, the Input Cost Bound;
- `O_c` be 8,000 for a Requirements call or 16,000 for a Draft call; and
- `ceil_div(n,d) = (n+d-1)//d`.

The call must satisfy `I_c + O_c <= 1,000,000` before transmission. Its whole worst-case reservation is:

```text
FlashRequirements(c) = ceil_div(I_c * 140,000, 1,000,000)
                     + ceil_div(8,000 * 280,000, 1,000,000)
                     = ceil_div(I_c * 140,000, 1,000,000) + 2,240 micros

ProDraft(c)          = ceil_div(I_c * 435,000, 1,000,000)
                     + ceil_div(16,000 * 870,000, 1,000,000)
                     = ceil_div(I_c * 435,000, 1,000,000) + 13,920 micros
```

For candidate `a`, with up to two independently rendered requests per stage:

```text
CandidateBound(a) = sum(FlashRequirements(c) for c in requirement calls 1..2)
                  + sum(ProDraft(c) for c in draft calls 1..2)
```

Every initial call, semantic repair, JSON repair, truncation recovery, and transport/rate/server recovery uses one of those two fixed stage slots. A proven pre-transmission failure releases its reservation but still consumes its dispatch slot. A sent or indeterminate attempt consumes a dispatch/transmission slot. No path restores a slot.

This is intentionally a per-render formula. Requirements requests contain the complete Job Content and Application Analysis; Draft requests contain the selected Master Resume evidence and derived requirements. Those source sizes are not globally bounded below the model context in current domain policy, so a smaller constant would be an unsupported estimate. A request whose next full reservation does not fit the remaining run ceiling must not be sent.

### Context-limit extrema (planning ceiling, not normal expected cost)

At the exact context boundary, `I = 1,000,000 - O`:

| Call | Maximum authorized `I` | Maximum reservation |
| --- | ---: | ---: |
| Flash Requirements, one call | 992,000 | 141,120 micros ($0.141120) |
| Flash Requirements, two calls | — | 282,240 micros ($0.282240) |
| Pro Draft, one call | 984,000 | 441,960 micros ($0.441960) |
| Pro Draft, two calls | — | 883,920 micros ($0.883920) |
| One candidate, all four calls | — | 1,166,160 micros ($1.166160) |

This maximum proves why the run ceiling cannot be chosen by multiplying a typical prompt size. Admission against the exact rendered request is what keeps the selected ceiling hard; a source can fit model context yet be unaffordable under the remaining ceiling.

## Exact request evidence and required rendering change

Current Resume messages are constructed in [`deepseek_resume.py`](../../../apps/api/merida_api/integrations/deepseek_resume.py):

- Requirements initial: system + user; repair: system + user + one user repair message. Its user message includes an SHA-256 delimiter, canonical compact JSON for the persisted Analysis (`summary`, `skillSignals`), and complete Job Content.
- Draft initial: system + user; repair: system + user + one user repair message. Its user message includes supported Requirement IDs and canonical compact JSON for `ResumeDraftInput`: target, supported requirements, fit score, category coverage, role targets, and up to seven selected evidence bullets per role.
- `JsonPromptPayloadEncoder` serializes structured source content with `ensure_ascii=False`, sorted keys, and compact separators; no source truncation occurs.

The accepted wire form must be rendered once and then sent byte-for-byte as:

```json
{
  "model": "deepseek-v4-flash or deepseek-v4-pro",
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "max_tokens": 8000,
  "response_format": {"type": "json_object"},
  "stream": false,
  "reasoning_effort": "high",
  "thinking": {"type": "enabled"}
}
```

The Pro draft uses `max_tokens:16000`; a repair adds only the third user message. Key ordering is irrelevant to provider semantics but the actual bytes measured must be the actual bytes sent.

The current Resume path cannot yet provide that evidence. It calls `ChatDeepSeek.ainvoke(messages)` and never exposes the body. The pinned `langchain-deepseek==1.1.0` delegates payload construction to `langchain-openai==1.3.5`; its defaults include model, `stream:false`, `max_tokens`, optional temperature/reasoning/extra body, then add converted messages, while `.bind(response_format=...)` adds JSON mode. The OpenAI SDK receives provider-specific `thinking` under `extra_body`. For cost authorization, Resume Generation should reuse the Analysis prepared-request seam that constructs canonical JSON itself and sends exactly those bytes, rather than trying to reconstruct opaque SDK serialization afterward. [Pinned LangChain DeepSeek 1.1.0 artifact and hash](https://pypi.org/pypi/langchain-deepseek/1.1.0/json) [Pinned LangChain OpenAI 1.3.5 artifact](https://pypi.org/pypi/langchain-openai/1.3.5/json)

## Tokenizer and protocol proof

Use the same conservative policy shape as Analysis:

```text
Input Cost Bound = max(pinned-tokenizer count of complete body,
                       complete UTF-8 body byte count)
                 + reviewed protocol overhead
```

The byte branch is a genuine upper bound for ordinary UTF-8 content under a byte-level BPE tokenizer; it also makes authorization conservative when exact provider-side tokenization differs. The tokenizer branch protects against special-token/protocol behavior. Character ratios are not admissible.

The existing [Analysis rate card](../../../apps/api/merida_api/features/applications/analysis_rate_card.v1.json) pins the official Flash tokenizer and DeepSeek V4 encoder at revision `60d8d70770c6776ff598c94bb586a859a38244f1`; its reviewed overhead is 27 tokens for JSON response-format wrapping plus the largest three-message request. The official Pro repository currently resolves to revision `b5968e9190ef611bbf34a7229255be88a0e937c1`. Its `tokenizer.json` SHA-256 is `8f9f37ca37fdc4f5fd36d5cf4d3b0e8392edb4e894fd10cc0d70b4957c8633cf`, and its `encoding/encoding_dsv4.py` SHA-256 is `bdbd57c132a1b3725042323d02b98b9d1df28e5f388f134399555d041f5055e0`; these match the tokenizer/encoder source hashes already recorded for Flash. This supports sharing the immutable tokenizer artifact, but the Pro endpoint/model still needs its own reviewed rate-card entry and explicit protocol-overhead approval. [Official Flash tokenizer](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/blob/60d8d70770c6776ff598c94bb586a859a38244f1/tokenizer.json) [Official Flash encoder](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/blob/60d8d70770c6776ff598c94bb586a859a38244f1/encoding/encoding_dsv4.py) [Official Pro tokenizer](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/b5968e9190ef611bbf34a7229255be88a0e937c1/tokenizer.json) [Official Pro encoder](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/b5968e9190ef611bbf34a7229255be88a0e937c1/encoding/encoding_dsv4.py)

The implementation should record the verified `H_requirements` and `H_draft` in the Resume rate card. Both largest requests contain the same three roles (system, user, user repair) and the same JSON response wrapper, so 27 is the evidence-backed candidate value, but it remains **unapproved for Resume/Pro until a reviewed test derives it from the pinned encoder**. Until that entry exists, authorization must fail closed; arithmetic must not silently substitute `27`.

## Batch projections for target 1–10

The Candidate Set is fixed at `min(queue size, 2 * target)`. Let `C_a` be the exact four-slot `CandidateBound(a)` computed from candidate `a`'s rendered calls (or the conservative planning maximum 1,166,160 micros). The bound for a particular fixed set is `sum(C_a)`. The following table shows the largest set size and the absolute context-bound planning exposure; the chosen Resume Run Spend Ceiling remains a separate human decision and will normally admit only a prefix of these calls.

| Target | Max candidates | Context-bound exposure (micros) | USD |
| ---: | ---: | ---: | ---: |
| 1 | 2 | 2,332,320 | $2.332320 |
| 2 | 4 | 4,664,640 | $4.664640 |
| 3 | 6 | 6,996,960 | $6.996960 |
| 4 | 8 | 9,329,280 | $9.329280 |
| 5 | 10 | 11,661,600 | $11.661600 |
| 6 | 12 | 13,993,920 | $13.993920 |
| 7 | 14 | 16,326,240 | $16.326240 |
| 8 | 16 | 18,658,560 | $18.658560 |
| 9 | 18 | 20,990,880 | $20.990880 |
| 10 | 20 | 23,323,200 | $23.323200 |

These are safe extrema, not predictions. For an operator-relevant ceiling proposal, record exact byte/token counts from representative fixture corpora and show distributional costs separately; do not weaken authorization based on those samples.

## Settlement and indeterminate calls

DeepSeek's non-streaming response supplies `id`, exact `model`, `finish_reason`, and `usage`: `prompt_tokens`, `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens`, `completion_tokens`, `total_tokens`, and `completion_tokens_details.reasoning_tokens`. DeepSeek specifies `prompt_tokens = cache hit + cache miss`, and charges output tokens without excluding reasoning. [DeepSeek Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion) [DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache)

Resume Generation can reuse [Analysis settlement rules](../../../apps/api/merida_api/features/applications/analysis_spend.py) and [`DeepSeekCallEvidence`](../../../apps/api/merida_api/integrations/deepseek.py) fields:

- only settle downward when request ID is nonempty, returned model equals the approved exact model, positive input/output counts reconcile, cache hit plus cache miss equals prompt tokens, total equals input plus output, reasoning tokens do not exceed output, and usage stays within the reservation;
- calculate verified cost using cache-hit and cache-miss rates plus the reasoning-inclusive completion count, with integer ceiling rounding;
- release the whole reservation only for a proven pre-transmission failure;
- if a call may have been sent but has missing, malformed, mismatched, or out-of-bound evidence, mark it indeterminate and leave its **entire worst-case reservation committed**. A fresh call needs a new slot and a separate full authorization.

The direct prepared HTTP adapter already captures this evidence. The legacy Resume `request_json` path discards it and classifies retry failures without trustworthy per-send receipts, so it cannot safely settle or reconstruct spend.

## Reuse assessment

The Analysis abstractions are suitable as a shared kernel, but their names and policy constants are not:

- Reuse: immutable reviewed rate-card entries keyed by exact endpoint/model; 30-day approval; pinned tokenizer/hash checks; canonical request fingerprint; greater-of-tokenizer/UTF-8 bound; integer micros and ceiling division; context admission; transactional reserve-before-send; evidence validation; conservative settlement; active/verified/indeterminate Committed Spend presentation.
- Generalize: `ApprovedAnalysisModel`, `AnalysisCostEstimate`, `AnalysisUsageReceipt`, `AnalysisSettlement`, and the pure estimate/settle mechanics into provider-spend types that both owning contexts can call. Keep transaction ownership and run ledgers in Applications and Resumes respectively.
- Do not reuse unchanged: Analysis's single Flash entry, hard-coded 8,000 output check, three-message field names, $0.50 ceiling, Analysis outcome names, or Analysis-owned SQLite tables.
- Resume-specific approval needs two exact entries: Flash/8,000 and Pro/16,000, each with current rates, context, tokenizer/protocol evidence, verification window, and independent approval fingerprint.

## Unsafe current-path baseline (not an accepted envelope)

Current nested loops can cause up to 18 transmissions for one candidate:

- Requirements: two semantic attempts × three hidden transport attempts = 6 Flash calls at 8,000.
- Draft: two semantic attempts × (three Flash attempts followed after terminal provider error by up to three Pro attempts) = up to 6 Flash calls at 16,000 plus 6 Pro calls at 8,000.

Ignoring input costs, that output-only exposure is `6*2,240 + 6*4,480 + 6*6,960 = 82,080` micros ($0.082080). Its complete bound still requires every exact rendered input. More importantly, the fallback only runs after three failed Flash sends and can itself retry three times, while the legacy client discards usage evidence. This baseline is therefore unsuitable for a hard run ceiling even though its output-only number looks small.

## Required readiness evidence

Before Resume calls may dispatch:

1. Implement and test exact render-once/send-once for the accepted request shape and capture model/request/finish/usage evidence.
2. Add reviewed Flash/8k and Pro/16k Resume rate-card entries. Pin the tokenizer artifacts and derive the three-message protocol overhead for both exact models; fail closed while either is absent, stale, or mismatched.
3. Prove stage and candidate call-slot enforcement at two/two/four, including proven-pre-send, sent, truncated, malformed, and indeterminate outcomes.
4. Prove atomic reservation before transmission and that all uncertain evidence stays fully committed across cancellation and restart.
5. Set the Resume Run Spend Ceiling only after comparing representative exact-render costs with the safe extrema above; do not copy Analysis's $0.50 policy without that decision.

No paid provider calls were made for this research.
