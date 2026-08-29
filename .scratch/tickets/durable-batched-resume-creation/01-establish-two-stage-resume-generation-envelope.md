# Establish the two-stage Resume Generation Envelope

Parent: [Wayfinder: Durable Batched Resume Creation](map.md)

Type: research

Status: ready-for-agent

State: closed

Assignee: codex

Blocked by: none

## Question

What exact DeepSeek endpoint and model capabilities can Merida rely on separately for Fit Requirement extraction and Resume Draft generation—including thinking mode and effort, reasoning-inclusive output and context limits, non-streaming behavior, connection/read/absolute deadlines, finish/model/request/usage evidence, and supported fallback behavior—so every initial, retry, repair, truncation, and fallback transmission is explicitly counted without silently lowering quality?

The resolution should distinguish verified provider facts from recommendations, identify a bounded transmission policy for each stage and the candidate as a whole, state whether the existing Flash-to-Pro fallback remains valid, and link a Markdown research asset based on high-trust primary sources and representative recorded probes.

## Answer

The primary-source and local-code findings are recorded in [Research: Two-stage Resume Generation Envelope](research-two-stage-resume-generation-envelope.md).

Use this Resume Generation Envelope:

| Dimension | Fit Requirement extraction | Resume Draft generation |
| --- | --- | --- |
| Endpoint | `https://api.deepseek.com/v1/chat/completions` | `https://api.deepseek.com/v1/chat/completions` |
| Model | `deepseek-v4-flash` | `deepseek-v4-pro` |
| Thinking | explicitly enabled at `high` effort | explicitly enabled at `high` effort |
| Generated-token ceiling | 8,000, including reasoning | 16,000, including reasoning |
| Dispatch-attempt ceiling | 2: initial plus at most one recovery | 2: initial plus at most one recovery |
| Model fallback | none | none |

Both stages use JSON object mode, explicitly non-streaming requests, 10-second connect and pool timeouts, 120-second write and read-inactivity timeouts, and a 300-second absolute deadline. The candidate-wide budget is four durable dispatch attempts. Initial generation, transport recovery, truncation recovery, malformed-output recovery, and semantic repair all consume the same stage slots; there is no nested retry loop, restored slot, model switch, disabled thinking, lowered effort, or raised token ceiling.

DeepSeek's official documentation verifies that both exact models support the endpoint, JSON mode, high-effort thinking, a one-million-token context, and provider output limits above these product bounds. A usable response must preserve safe evidence for transmission state, body completion ID, returned model, finish reason, prompt/completion/cache/total usage, and reasoning-token count. Only a `stop` response that passes JSON and semantic validation completes a stage; sent or indeterminate failures consume a slot and retain conservative spend unless trustworthy evidence settles them.

Retire the existing Flash-primary-to-Pro fallback. It currently changes model, quality, output cap, timeout, and price only after an error, can retry non-retryable failures, and combines with semantic and hidden transport retries to permit 18 transmissions per candidate. There is no provider guarantee or recorded Resume corpus establishing Flash and Pro as interchangeable draft authors.

The repository has deterministic provider seams but no saved first-party V4 Resume responses. Production readiness must therefore fail closed until sanitized recorded-provider probes verify both exact stage envelopes, safe response evidence, timeout behavior, and the absence of hidden retries. This is an evidence gate, not permission to change the envelope dynamically.
