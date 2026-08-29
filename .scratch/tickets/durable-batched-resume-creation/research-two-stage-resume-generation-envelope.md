# Research: Two-stage Resume Generation Envelope

Verified: 2026-08-13

This note answers the provider-envelope question for durable batched Resume Creation. It separates current provider facts, current Merida behavior, and the recommended product policy. No paid provider call was made for this research.

## Decision-ready answer

Adopt one explicit, non-streaming, thinking-enabled envelope with no model fallback:

| Dimension | Fit Requirement extraction | Resume Draft generation |
| --- | --- | --- |
| Endpoint | `https://api.deepseek.com/v1/chat/completions` | `https://api.deepseek.com/v1/chat/completions` |
| Model | `deepseek-v4-flash` | `deepseek-v4-pro` |
| Thinking | `thinking: {"type":"enabled"}` | `thinking: {"type":"enabled"}` |
| Effort | `reasoning_effort: "high"` | `reasoning_effort: "high"` |
| Structured output | `response_format: {"type":"json_object"}` | `response_format: {"type":"json_object"}` |
| Transport | `stream: false` | `stream: false` |
| Generated-token ceiling | 8,000, including reasoning | 16,000, including reasoning |
| Dispatch-attempt ceiling | 2 total: initial plus at most one recovery | 2 total: initial plus at most one recovery |
| HTTP timeout | connect 10s; pool 10s; write 120s; read inactivity 120s | connect 10s; pool 10s; write 120s; read inactivity 120s |
| Absolute deadline | 300s from invocation | 300s from invocation |
| Model fallback | none | none |

The candidate-wide ceiling is four dispatch attempts and therefore no more than four possible provider transmissions: two for extraction and two for drafting. A proven pre-transmission failure releases its spend reservation but still consumes its stage's dispatch-attempt slot. A sent or indeterminate attempt consumes the slot and remains charged or reserved according to settlement evidence. No path restores a slot, changes model, disables thinking, lowers effort, or raises the token ceiling.

This table is a **product recommendation**, not a claim that these lower output limits or deadlines are provider defaults. It deliberately fixes quality and cost behavior for every initial, retry, repair, truncation, and recovery call.

## Verified DeepSeek facts

### Endpoint and model capabilities

DeepSeek's current Chat Completions API accepts `deepseek-v4-flash` and `deepseek-v4-pro`. First-party integration documentation shows the full OpenAI-compatible URL as `https://api.deepseek.com/v1/chat/completions`; the V4 change log identifies both exact model IDs and says the base URL is unchanged. Both IDs are therefore valid on the same provider endpoint. [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion), [WorkBuddy/CodeBuddy integration](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy/), [DeepSeek V4 change log](https://api-docs.deepseek.com/updates/)

Both models support a one-million-token context, up to 384,000 generated tokens, JSON Output, thinking and non-thinking modes, and Chat Completions. Those are provider maxima, not sensible Resume defaults. The provider also describes Flash as the faster, economical model that approaches Pro on reasoning and simple agent work, while describing Pro as the stronger knowledge and complex-reasoning model; it does not claim the models are quality-equivalent for Resume drafting. [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/), [DeepSeek V4 release](https://api-docs.deepseek.com/news/news260424/)

The request field is `max_tokens`. DeepSeek defines it as the maximum generated completion length and constrains input plus generated tokens to the model context. The response usage schema nests `reasoning_tokens` inside `completion_tokens_details`, so the conservative interpretation is that reasoning consumes the same generated-token and billed-output envelope. The product must reserve the full `max_tokens` value rather than assuming a smaller visible JSON body. [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion)

### Thinking and JSON behavior

Thinking defaults to enabled and regular requests default to `high`; the only native effort values are `high` and `max`. Compatibility values `low` and `medium` map to `high`, while `xhigh` maps to `max`. Merida should nevertheless send both fields explicitly so the quality contract is visible and testable. [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)

DeepSeek says temperature, `top_p`, and the penalty fields have no effect in thinking mode. The recommended request therefore omits them rather than retaining the current Resume path's `temperature: 0`. [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)

JSON Output requires `response_format: {"type":"json_object"}` plus an instruction and example containing JSON. DeepSeek warns that JSON mode can still return empty content and that too small a `max_tokens` can truncate JSON, so provider JSON mode does not replace Pydantic and semantic validation or a bounded repair call. Merida's existing prompts already request JSON and include examples. [JSON Output](https://api-docs.deepseek.com/guides/json_mode/), [current Resume prompts](../../../apps/api/merida_api/integrations/deepseek_resume.py#L48-L120)

### Safe response and failure evidence

A non-streaming success schema provides a required body `id`, exact response `model`, `choices[].finish_reason`, and usage containing prompt, completion, total, cache-hit, cache-miss, and reasoning-token counts. The documented finish reasons are `stop`, `length`, `content_filter`, `tool_calls`, and `insufficient_system_resource`. Only `stop` followed by successful JSON and semantic validation can complete a stage; every other transmitted outcome consumes a slot. `length` can mean either the requested output ceiling or total context was exhausted. [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion)

The provider schema guarantees the body completion `id`, but it does not guarantee either `x-request-id` header currently checked by Merida. Settlement should therefore accept the required body `id` as request identity, while headers may remain optional corroboration. The response `model` must be recorded as returned and must not be synthesized from the requested model. [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion), [current evidence extraction](../../../apps/api/merida_api/integrations/deepseek.py#L274-L319)

DeepSeek documents 400/422 as request defects, 401 as authentication failure, 402 as insufficient balance, 429 as rate limiting, and 500/503 as retryable service conditions. A retry is permitted only while the current stage still has its one recovery slot; authentication, balance, and request defects do not switch models or retry. [Error Codes](https://api-docs.deepseek.com/quick_start/error_codes/)

### Non-streaming requests and deadlines

The API is non-streaming by default, and `stream: false` returns one completion object. DeepSeek can send empty-line keep-alives while a non-streaming request waits, and it may keep that connection queued for as long as ten minutes before closing it if inference has not begun. Merida should send `stream: false` explicitly and use its own shorter absolute deadline. [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion), [Rate Limit & Isolation](https://api-docs.deepseek.com/quick_start/rate_limit/), [DeepSeek FAQ](https://api-docs.deepseek.com/faq)

HTTPX distinguishes connect, pool, write, and read-inactivity timeouts; a read timeout is the interval without a received response chunk, not a whole-request deadline. Provider keep-alives can therefore refresh read activity. Python's `asyncio.wait_for` supplies the independent elapsed-time bound, although cancellation completion can make observed wall time slightly exceed the configured value. [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/), [Python `asyncio.wait_for`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for)

## Local observations

### Current stage and fallback topology

Merida currently defaults `ANALYSIS_MODEL` to Flash and `RESUME_MODEL` to Pro, then passes both values into the Resume builder. [settings](../../../apps/api/merida_api/core/settings.py#L24-L35), [composition root](../../../apps/api/merida_api/app.py#L376-L386)

The current builder uses:

- Flash with 8,000 `max_tokens` and a scalar 120-second timeout for Fit Requirements;
- Flash with 16,000 `max_tokens` and a scalar 180-second timeout as the primary Resume Draft model;
- Pro with 8,000 `max_tokens` and the client's default scalar 30-second timeout only after a `DeepSeekProviderError` from Flash.

This means the configured Resume model is not used on an ordinary successful draft. The fallback catches every normalized provider error, including non-retryable authentication, balance, and invalid-request failures. [Resume client construction and fallback](../../../apps/api/merida_api/integrations/deepseek_resume.py#L160-L205), [provider error classification](../../../apps/api/merida_api/integrations/deepseek.py#L419-L481), [composition test](../../../apps/api/tests/test_deepseek_resume.py#L58-L100)

When passed as a scalar through the pinned `langchain-deepseek`/OpenAI/HTTPX stack, each current Resume timeout applies equally to connect, read, write, and pool. That makes the Pro fallback much more likely to time out at 30 seconds than either Flash call. This was confirmed locally by constructing the pinned client without sending a request; it reported 120/120/120/120, 180/180/180/180, and 30/30/30/30 seconds respectively. The HTTPX meaning of each dimension is documented independently. [client construction](../../../apps/api/merida_api/integrations/deepseek.py#L202-L245), [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/)

### Current retry multiplication

The legacy Resume client owns as many as three transport invocations per higher-level call. Fit Requirement extraction has two semantic attempts, so it can transmit six times. Resume Draft has two semantic attempts, and each can exhaust three Flash invocations before the fallback exhausts three Pro invocations, so drafting can transmit twelve times. A pathological candidate can therefore cause eighteen provider transmissions. [legacy transport loop](../../../apps/api/merida_api/integrations/deepseek.py#L90-L118), [two Fit Requirement attempts](../../../apps/api/merida_api/features/resumes/resume_builder.py#L345-L386), [two Resume Draft attempts](../../../apps/api/merida_api/features/resumes/resume_builder.py#L249-L287), [fallback](../../../apps/api/merida_api/integrations/deepseek_resume.py#L160-L178)

The legacy `request_json` path returns only a dictionary. It discards finish reason, actual model, completion identity, all usage, and transmission state; it also does not apply the client's 300-second `asyncio.wait_for` deadline or reject a `length` finish reason explicitly. Those controls exist only in the newer one-call/prepared transport used by Application Analysis. [legacy versus one-call paths](../../../apps/api/merida_api/integrations/deepseek.py#L90-L199), [safe evidence extraction](../../../apps/api/merida_api/integrations/deepseek.py#L360-L436)

### Recorded evidence available in this repository

The Resume tests use deterministic in-memory model responses and assert the current model/token/timeout wiring and semantic repair, but they do not contain a saved first-party HTTP response from either V4 model. The Analysis tests provide a useful deterministic evidence seam for finish reason, model, request identity, cache usage, and reasoning-token omission, but that evidence is synthetic rather than a live-provider recording. [Resume recorded model](../../../apps/api/tests/test_deepseek_resume.py#L39-L55), [Resume wiring test](../../../apps/api/tests/test_deepseek_resume.py#L58-L100), [Analysis evidence seam](../../../apps/api/tests/test_deepseek_analysis.py#L263-L321)

Four relevant deterministic tests were run during this research and passed: Resume wiring, Resume semantic repair, explicit high-thinking Analysis wiring, and safe Analysis response evidence. No external transmission occurred.

## Recommended policy and rationale

### Stage selection

Use Flash only for Fit Requirement extraction. Its output is bounded to at most 40 small typed records, and the existing product already assigns the Analysis model to this stage. Keep the current 8,000-token ceiling, but make thinking/high explicit and require a sanitized recorded-provider acceptance probe before production readiness. [Fit Requirement schema](../../../apps/api/merida_api/features/resumes/ports.py#L79-L106), [current requirement client](../../../apps/api/merida_api/integrations/deepseek_resume.py#L181-L189)

Use Pro for every Resume Draft call, not merely as an error fallback. Drafting is the quality-sensitive, longer-form stage and may return up to 30 roles with seven evidence-grounded bullets apiece. Preserve the current primary draft allowance of 16,000 generated tokens, make thinking/high explicit, and bound or reject inputs whose conservatively projected response cannot fit instead of truncating source data or changing the envelope. [Generated Resume schema](../../../apps/api/merida_api/features/resumes/ports.py#L109-L134), [current 16,000-token draft client](../../../apps/api/merida_api/integrations/deepseek_resume.py#L190-L195)

The 8,000/16,000 values are approved **product bounds**, not demonstrated minimums. The repository has no representative real Resume response proving them. Before the durable flow reports Resume provider readiness, record at least one sanitized success for each exact endpoint/model/envelope and one controlled `length`/invalid-output response at the adapter seam. If representative source structure cannot reliably fit these caps, reopen the cap or narrow the accepted source/output contract; do not silently disable thinking or increase cost at runtime.

### Call counting and recovery

Give each stage exactly two durable dispatch-attempt slots. The first is normal generation; the second may be used for one of: a transient transport/429/5xx recovery, length/empty/malformed JSON recovery, or semantic repair. A recovery cannot create an additional nested transport retry. Draft recovery always remains Pro/16K/high-thinking, and requirement recovery always remains Flash/8K/high-thinking.

Every attempt reserves its exact rendered request before dispatch. Proven pre-transmission failure releases the reservation but consumes the dispatch slot; this is stricter than a renewable transmission-only counter and keeps elapsed work finite. A response, provider HTTP status, write/read failure after dispatch, absolute deadline, cancellation during dispatch, or otherwise ambiguous failure is sent or indeterminate and consumes the full reservation unless trustworthy matching usage settles it downward.

The stage ordering means a candidate can spend at most two Flash calls before eligibility/evidence gates, followed only when allowed by at most two Pro calls. If extraction exhausts its stage, Draft has zero transmissions. This is the complete candidate transmission graph:

```text
Requirements: Flash initial -> optional Flash recovery -> validate/gate
Draft:        Pro initial   -> optional Pro recovery   -> validate/deterministic completion
Candidate:    at most 2 Flash + 2 Pro = 4 provider transmissions
```

### Why the current Flash-to-Pro fallback should not remain

The provider supports both model IDs, so the calls are syntactically valid, but the current fallback is not a valid durable policy:

- it silently makes Flash—not the configured Resume model—the normal author of the draft;
- it changes model, output ceiling, timeout, unit price, and likely quality only after an error;
- it can retry non-retryable authentication, balance, and request failures on the same endpoint;
- it multiplies one semantic attempt into six transmissions;
- it has no provider guarantee that Pro is an availability failover for Flash; and
- there is no recorded Resume corpus proving that Flash and Pro satisfy one interchangeable quality contract.

Retire the fallback. A future fallback may be added only as a separately researched and approved envelope with explicit quality equivalence, price authority, trigger conditions, call accounting, and recorded probes. It must never be introduced as an implicit recovery branch.

### Wire evidence and privacy

For every completed response, capture only: transmission state, body completion `id`, returned model, finish reason, prompt/completion/total tokens, cache-hit/cache-miss input tokens, and reasoning-token count. Never persist, log, or return `reasoning_content`, prompt bodies, Job Content, Master Resume content, or generated Resume text in the durable coordination store. The existing prepared Analysis transport already demonstrates the intended safe metadata shape, but the Resume path must own its stage identity and exact model/output bound. [DeepSeek response schema](https://api-docs.deepseek.com/api/create-chat-completion), [current safe evidence type](../../../apps/api/merida_api/integrations/deepseek.py#L16-L36), [Analysis omission test](../../../apps/api/tests/test_deepseek_analysis.py#L263-L321)

## Remaining uncertainty and readiness gate

Provider documentation establishes that both exact models support this protocol, but documentation does not prove application-specific output quality or latency under Merida's prompts. The absence of real saved Resume provider probes is the only unresolved empirical gap. It does not require a different planning envelope; it requires a fail-closed readiness check before deployment:

1. verify current approval for the exact endpoint/model pair and output bound;
2. replay sanitized representative Fit Requirement and multi-role Draft requests through the exact prepared-request transport;
3. record only request envelope fields and safe response evidence, never reasoning or private content;
4. prove `stream: false`, thinking/high, JSON mode, finish/model/id/usage capture, the timeout layers, and no hidden retry; and
5. block Resume Run start if either stage lacks current pricing/model approval or its probe contract fails.

Cost arithmetic, tokenizer/protocol bounds, and the fixed Resume Run Spend Ceiling are intentionally resolved by the dependent cost and grilling tickets, using this four-transmission envelope.
