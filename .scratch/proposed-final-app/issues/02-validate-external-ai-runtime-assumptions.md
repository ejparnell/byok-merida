# Validate the external AI and runtime dependency assumptions

Type: research
Status: resolved
Blocked by: none
Map: [Make the Merida final app implementation-ready](../map.md)

## Problem Statement

Merida's reviewed final-app contracts rely on FastAPI, Pydantic, LangGraph, a DeepSeek integration, TOON prompt encoding, and OpenAPI TypeScript generation. Those contracts deliberately describe the product behavior and Merida-owned boundaries, but they do not yet prove that a mutually compatible, currently supported dependency set can implement them.

Without that proof, the implementation plan could freeze unavailable DeepSeek model names, a provider integration that cannot enforce Merida's retry and JSON-output rules, a graph runtime that cannot carry the proposed serializable state and injected context, an unmaintained TOON library, or an API generator that does not produce a usable client for both the dashboard and extension. Any of those discoveries after implementation begins would force an architectural rewrite or weaken evidence and privacy guardrails.

## Solution

Produce a dated runtime-compatibility decision record backed by primary-source evidence and a small executable conformance suite. The research must identify a pinned, mutually compatible Python and TypeScript dependency set—or explicitly reject an assumption and name the smallest contract-preserving substitute.

The single acceptance seam is Merida's public runtime-adapter boundary. The suite proves, through externally observable behavior, that a candidate stack can:

- host typed HTTP and OpenAPI contracts;
- execute one bounded, context-injected graph invocation;
- make a DeepSeek structured-output request with only Merida-owned retry policy;
- encode the curated prompt DTO through the selected TOON or JSON encoder;
- generate and consume a typed OpenAPI client from the same contract.

Feature workflows, Notion persistence, PDF rendering, and real credentials remain outside the conformance suite. They retain their existing contracts and are not used to prove package compatibility.

## User Stories

1. As a Merida maintainer, I want a verified supported dependency set, so that implementation begins from compatible runtime assumptions.
2. As a Merida maintainer, I want each runtime conclusion dated and linked to primary evidence, so that future upgrades can distinguish fact from a stale planning assumption.
3. As a backend implementer, I want FastAPI and Pydantic versions verified together, so that typed route contracts and generated OpenAPI are dependable.
4. As a backend implementer, I want a supported Python-version range recorded, so that the selected runtime can be reproduced locally and in CI.
5. As a workflow implementer, I want LangGraph support for bounded `StateGraph` execution confirmed, so that Application Analysis and Resume Creation can remain explicit, feature-owned graphs.
6. As a workflow implementer, I want graph state serializability and runtime-context injection validated, so that credentials, clients, prompts, and loggers stay outside durable state.
7. As a workflow implementer, I want terminal outcomes to emerge as typed values rather than uncaught framework exceptions, so that route behavior remains stable.
8. As a Merida operator, I want Application Analysis and Resume Creation to remain DeepSeek-first, so that the product does not gain an unnecessary provider platform.
9. As a backend implementer, I want the selected DeepSeek path to support the documented JSON-output behavior, so that model drafts can be parsed into Pydantic models before evidence validation.
10. As a backend implementer, I want the provider integration to permit library retries to be disabled, so that transport retries occur only within Merida's bounded retry policy.
11. As a backend implementer, I want provider errors classified at the adapter boundary, so that authentication, unsupported-model, rate-limit, timeout, and server failures follow the correct retry rules.
12. As a Merida operator, I want the configured analysis and resume model identifiers verified against current provider documentation, so that startup validation does not advertise unavailable models.
13. As a Merida operator, I want any unavailable or unsupported proposed model identifier replaced explicitly, so that a silent model substitution cannot change workflow quality or cost.
14. As a privacy-conscious operator, I want real credentials and private Application or Master Resume content excluded from compatibility fixtures, so that runtime validation is safe to run locally and in CI.
15. As a prompt-engineering maintainer, I want TOON to remain an input-only, replaceable encoding choice, so that application state, HTTP contracts, persisted data, and model output remain typed JSON-compatible values.
16. As a prompt-engineering maintainer, I want every accepted TOON encoder to pass specification and Merida escaping cases, so that untrusted content cannot corrupt a prompt data block.
17. As a prompt-engineering maintainer, I want JSON encoding retained as an explicit rollback implementation, so that an encoder failure never triggers an invisible per-request format change.
18. As a Merida maintainer, I want a clear decision when no external TOON package meets the conformance bar, so that a narrow internal encoder can be chosen deliberately rather than adopting stale tooling.
19. As a frontend implementer, I want the OpenAPI generator and TypeScript runtime verified against FastAPI's emitted schema, so that the dashboard and extension share one contract interpretation.
20. As a frontend implementer, I want generated client output to preserve typed success and error payloads, so that UI code need not infer backend result shapes.
21. As an extension implementer, I want client generation to support the `X-Capture-Token` request boundary without exposing backend secrets, so that Capture uses the same contract safely.
22. As a Merida operator, I want one final response for each dashboard action preserved during runtime validation, so that compatibility work does not reintroduce streamed-progress transport.
23. As a migration implementer, I want the compatibility suite to run with deterministic fake adapters, so that provider availability and Notion state cannot make version checks flaky.
24. As a migration implementer, I want one documented lockfile-compatible resolution, so that a new checkout can install the verified stack exactly.
25. As a reviewer, I want rejected versions, integrations, and model assumptions recorded with reasons, so that later work does not accidentally restore an invalid option.
26. As a reviewer, I want unresolved external uncertainty called out as a blocker to dependent API and topology decisions, so that downstream tickets do not claim false certainty.
27. As a future upgrade owner, I want a repeatable conformance command and evidence refresh rule, so that upgrades can be evaluated without rediscovering the architectural boundary.

## Implementation Decisions

- This work is research and decision capture. It does not implement the FastAPI application, React dashboard, React extension, LangGraph production workflows, workspace adapter, PDF exporter, or migration.
- Treat the reviewed final-app AI workflow contract as the product authority: two independent, bounded, feature-owned graph invocations; sequential batch orchestration outside the graph; DeepSeek-first structured calls; deterministic evidence and score gates; one final HTTP response; and no private values in normal logs or browser responses.
- Treat package names, exact versions, provider SDK behavior, model identifiers, TOON implementation choice, and OpenAPI generator choice as assumptions to validate. Do not make any of them architectural facts solely because they appear in the reviewed documentation.
- Use a source hierarchy for every conclusion: official project documentation and release notes first; official package metadata, changelogs, repositories, and compatibility declarations second; a minimal local conformance result third. Community posts, package indexes, and model wrappers may identify candidates but cannot alone establish support.
- Record the research date, source URL, supported Python and Node ranges, candidate version, direct dependency constraints, transitive compatibility constraints when material, result, and rationale in a durable decision record. Mark each assumption `accepted`, `revised`, `rejected`, or `unresolved`.
- Verify FastAPI and Pydantic as one HTTP-schema boundary. The accepted pair must generate an OpenAPI document for representative request, response, validation-error, cursor, and typed workflow-outcome contracts without custom schema surgery.
- Verify LangGraph only through Merida's graph boundary: `StateGraph`, explicit start and terminal routing, conditional branching, serializable state, and injected runtime context. Durable checkpoint storage, human interrupts, and crash resumption are excluded from v1 and cannot become implicit requirements of the selected version.
- Keep the DeepSeek integration behind Merida's structured-output adapter. The accepted option must support explicit model selection, a request form that activates documented JSON output, access to response content and provider error information, and disabling or bypassing library-managed retries. If a LangChain integration cannot satisfy this, evaluate the official OpenAI-compatible HTTP API behind the same adapter before broadening provider scope.
- Validate each proposed DeepSeek model name independently. Acceptance requires primary provider evidence that the model is currently available through the selected API and supports the required structured-output invocation. Do not infer support from a similarly named model, a wrapper default, or a dashboard-only capability.
- Keep Merida's retry budget authoritative: at most two retryable transport retries and at most one structured-output repair call. The chosen integration must make nested SDK or framework retries impossible, disabled, or demonstrably outside the request path.
- Maintain the `PromptPayloadEncoder` as the sole TOON boundary. An accepted encoder must take a strict JSON-compatible prompt DTO and return its declared format, specification version, text, and byte counts. JSON remains a separately selected startup configuration for rollback, comparison, and tests; there is no silent call-level fallback.
- Evaluate TOON candidates against the reviewed v3.3 conformance expectation, Merida prompt DTO round trips, adversarial escaping cases, and controlled DeepSeek comparison metrics. If no candidate passes, recommend a deliberately narrow internal encoder for Merida's JSON-compatible prompt DTOs and pin the specification revision used by its fixtures.
- Keep prompt-format selection startup-owned. The research must verify that an encoding failure produces a typed technical failure before any model call, not a rewritten or truncated prompt.
- Verify an OpenAPI TypeScript generation path from the FastAPI-generated schema, not manually maintained TypeScript types. The exact generator is selected only if it can emit a consumable client for both React consumers, preserve documented operation and payload types, accept extension authentication headers through normal client configuration, and run in the selected Node and package-manager environment.
- The compatibility harness uses fake workspace, model, encoder, clock, and identifier adapters. A real provider smoke check may validate a candidate after local conformance passes, but it uses a non-sensitive minimal payload, is manually gated, records no prompt or response body, and is not required for ordinary CI.
- Pin accepted dependencies in the eventual backend and frontend lockfiles, with direct version constraints that prevent accidental incompatible upgrades. Do not introduce a package lockfile or repository topology in this ticket; that remains the runtime-topology decision's responsibility.
- Publish a compatibility matrix and decision log as the artifact of this ticket. Revise the reviewed proposed-final-app documents only where research disproves an existing dependency, model, or capability assumption; retain Merida-owned interfaces wherever a package substitution can preserve the contract.
- A rejected or unresolved required dependency assumption blocks the dependent public-API and runtime-topology tickets until the decision record names either a conforming alternative or a contract change.

## Testing Decisions

- A good compatibility test observes public adapter behavior and emitted contracts, not library internals, private methods, request object layouts, dependency injection containers, or exact generated source formatting.
- Use one runtime-adapter conformance suite as the highest common seam. It supplies a representative typed Application Analysis action and Resume Creation action to the assembled runtime boundary, then observes typed outcome, OpenAPI document, generated-client call behavior, retry count, selected prompt format, and absence of forbidden output.
- Test FastAPI and Pydantic through HTTP-level request validation, representative success and expected-blocked responses, and generated OpenAPI schemas. Assert semantic payload compatibility, not ordering or incidental schema metadata.
- Test LangGraph through an invocation that uses injected fake context, follows both a completed and blocked branch, returns a typed terminal outcome, and never serializes clients, credentials, prompt text, or exception objects into observable graph state.
- Test the DeepSeek adapter with a deterministic transport fake that exercises valid JSON, empty content, malformed JSON, schema-invalid JSON, retryable transport failure, non-retryable provider failure, and the single structured-output repair budget. Assert final typed results and model-call counts, never prompt wording.
- Add a separately gated, minimal real-provider smoke test only after primary-source evidence identifies a candidate model and API path. It must verify capability without storing credentials, full payloads, raw responses, or provider request identifiers.
- Test the prompt encoder with every prompt DTO and adversarial strings containing newlines, separators, quotes, backslashes, brackets, leading hyphens, Unicode, control characters, and numeric-looking text. Assert either a lossless accepted encoding or a typed pre-model failure; no string truncation or silent JSON fallback is permitted.
- Test the OpenAPI generator by generating a client from the representative FastAPI schema and invoking it against the conformance application. Assert typed handling for success, expected workflow block, and validation error responses, plus configuration of the extension's capture-token header.
- Test the assembled dependency resolution in a clean environment using the selected supported Python and Node versions. This is a reproducibility check, not a full product build.
- Reuse the repository's focused workflow, adapter, evidence-validation, and parity-test style: deterministic dependencies, semantic outcomes and effects, explicit forbidden effects, and no dependence on live Notion or personal source data.

## Out of Scope

- Implementing production FastAPI routes, Pydantic domain schemas, React screens, Chrome extension code, LangGraph workflows, Notion compatibility mappings, PDF export, or migration slices.
- Selecting the final module ownership model, repository topology, public route namespace, exact public request and response schemas, concurrency policy, recovery policy, or demo-mode acceptance rules.
- Building a multi-provider LLM abstraction, a dashboard model picker, a general agent runtime, tools, human graph interrupts, durable graph checkpoints, or automatic crash resumption.
- Treating raw provider output, exact prompt text, model quality, token cost, latency targets, or PDF content as golden compatibility snapshots. The controlled TOON comparison may record aggregate metrics for a decision, but it does not establish product-quality acceptance.
- Renaming existing Notion databases, properties, relations, or records, or changing evidence guardrails, queue eligibility, idempotency, cleanup semantics, or privacy requirements.
- Promoting an external package because it is popular, has a convenient wrapper, or appears in an older planning document without evidence that it satisfies this spec.

## Further Notes

- The resolved compatibility matrix and executable runtime-adapter conformance fixture are published in [the research asset](../assets/external-ai-runtime-compatibility.md). Its JSON-default decision updates the reviewed AI workflow contract without changing workflow, evidence, API, or persistence behavior.
- The outcome of this research is allowed to revise or reject the currently proposed `langchain-deepseek`, `deepseek-v4-flash`, `deepseek-v4-pro`, TOON-v3.3, and OpenAPI-generation assumptions. It should preserve the reviewed workflow and adapter contracts whenever a substitution can do so.
- The accepted dependency matrix is an input to the public API/client and runtime/repository-topology decisions. It does not prematurely decide either ticket's broader design.
- The parity inventory remains the migration behavior authority. This specification only proves that the target runtime can support those preserved and target-addition behaviors; it does not replace parity fixtures.
- Refresh the decision record before an implementation lockfile upgrade, a supported Python or Node upgrade, a provider model retirement, an SDK integration replacement, or a TOON specification revision.
