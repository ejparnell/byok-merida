# External AI Runtime Compatibility Decision

Research date: July 10, 2026  
Decision owner: proposed-final-app issue 02  
Scope: FastAPI, Pydantic, LangGraph, DeepSeek, TOON, and generated OpenAPI TypeScript clients.

## Decision

Accept the following v1 runtime baseline, subject to an implementation lockfile resolving the listed direct pins:

| Concern | Accepted baseline | Result |
| --- | --- | --- |
| Python runtime | Python 3.14.2 for the evaluated environment; support Python 3.10 through 3.14 | accepted |
| HTTP and schema boundary | `fastapi==0.139.0`, `pydantic==2.13.4` | accepted |
| Graph runtime | `langgraph==1.2.8` | accepted |
| DeepSeek integration | `langchain-deepseek==1.1.0` with its resolved `langchain-openai==1.3.5` transitively | accepted with adapter guardrails |
| Analysis model | `deepseek-v4-flash` | accepted |
| Resume model | `deepseek-v4-pro` | accepted |
| Prompt format | JSON through `JsonPromptPayloadEncoder` | accepted for v1 |
| Python TOON implementation | No external package | rejected for v1 real mode |
| OpenAPI TypeScript generator | `@hey-api/openapi-ts@0.99.0` plus explicit `typescript@5.9.3` build dependency | accepted |
| Node runtime | Node 22 or newer; evaluated with Node 25.8.1 | accepted |

The contract-preserving revision is that v1 uses JSON prompt encoding by default. TOON remains a future, explicit startup option only after a Python implementation passes the recorded conformance gate. No feature workflow, evidence rule, public HTTP contract, or persistence format changes as a result.

## Evidence And Findings

| Assumption | Evidence | Finding |
| --- | --- | --- |
| FastAPI and Pydantic can provide the typed HTTP/OpenAPI boundary. | [FastAPI PyPI metadata](https://pypi.org/project/fastapi/) declares Python 3.10+ and Pydantic 2 support; [Pydantic PyPI metadata](https://pypi.org/project/pydantic/) publishes the evaluated 2.13 line. | The evaluated versions install together on Python 3.14 and generate the representative OpenAPI document without schema customization. |
| LangGraph can support Merida's bounded state graph and injected dependency context. | [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) documents `StateGraph`, `TypedDict` state, terminal edges, and `context_schema`; [LangGraph PyPI](https://pypi.org/project/langgraph/) requires Python 3.10+. | The evaluated version invoked a typed graph with injected runtime context. It does not require a checkpointer for Merida's bounded v1 runs. |
| The proposed DeepSeek models and JSON output are available through the selected provider path. | [DeepSeek's V4 change log](https://api-docs.deepseek.com/updates/) documents `deepseek-v4-pro` and `deepseek-v4-flash` on the OpenAI Chat Completions interface. [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode) documents `response_format: {"type": "json_object"}` and the prompt requirements. | Both proposed model names remain valid. JSON Output is suitable for a typed draft, but the adapter must still reject empty, malformed, and schema-invalid content. |
| `langchain-deepseek` can remain behind Merida's structured-output adapter. | [Package metadata](https://pypi.org/project/langchain-deepseek/) publishes 1.1.0 for Python 3.10+; [ChatDeepSeek docs](https://docs.langchain.com/oss/python/integrations/chat/deepseek) document structured output and `max_retries`. | Constructing `ChatDeepSeek` with `max_retries=0` and creating a structured-output runnable succeeds. Merida retains all transport and repair retries at its own adapter boundary. A real-provider smoke check still belongs behind a manual credential gate. |
| TOON v3.3 is a stable enough Python dependency for v1. | The [official specification](https://toonformat.dev/reference/spec) identifies v3.3 as a current working draft. The [official TOON organization](https://github.com/orgs/toon-format/repositories) describes `toon-python` as community-driven. Its [open issues](https://github.com/toon-format/toon-python/issues) include current data-loss and round-trip defects and an open request for a stable PyPI release. | rejected. The proposed `TOON v3.3` dependency assumption is not accepted for real-mode v1. JSON remains the explicit encoder; a narrow internal encoder may be reconsidered only after the full fixture gate passes. |
| One generated TypeScript client can serve both React consumers. | [Hey API package documentation](https://www.npmjs.com/package/@hey-api/openapi-ts) states Node 22+, OpenAPI input, typed SDK/types, and Fetch-client support. | Version 0.99.0 generated a client from the representative FastAPI schema and the output typechecked under TypeScript 5.9.3. The generator requires TypeScript to be installed explicitly in the generation environment; retain it as a pinned dev dependency. |

## Executable Conformance

The companion `runtime-adapter-conformance.py` fixture exercises the only shared acceptance seam without a live Notion workspace or DeepSeek credential:

1. FastAPI validates a typed request, returns completed and blocked results, returns a validation error, and emits OpenAPI components.
2. LangGraph executes a `StateGraph` from start to terminal edge with runtime context injected outside graph state.
3. `ChatDeepSeek` accepts the selected V4 Flash identifier, disables library retries with `max_retries=0`, and creates a structured-output runnable.
4. The emitted OpenAPI schema generates a Hey API TypeScript client that typechecks.

The evaluated commands completed successfully:

```text
python runtime-adapter-conformance.py --openapi-json /tmp/openapi.json
npm exec --package=@hey-api/openapi-ts@0.99.0 --package=typescript@5.9.3 -- openapi-ts -i /tmp/openapi.json -o /tmp/generated-client
npm exec --package=typescript@5.9.3 -- tsc --noEmit --target es2022 --module nodenext --moduleResolution nodenext /tmp/generated-client/**/*.ts
```

The first generator-only invocation failed because `@hey-api/openapi-ts` accessed the TypeScript compiler at runtime. Including the explicit TypeScript package corrected that environment dependency. This is why the accepted baseline pins both packages.

The FastAPI test client emitted a Starlette deprecation warning about its current `httpx` integration. It did not affect contract generation or test results. Re-evaluate that warning when FastAPI or Starlette is upgraded; it is not a v1 blocker.

## Required Implementation Guardrails

- Build the DeepSeek request directly inside Merida's adapter, set JSON Output explicitly, set `max_retries=0`, and keep the documented two transport retries plus one repair attempt in Merida code.
- Validate the configured model identifiers at startup. Do not fall back from either V4 model to legacy aliases silently.
- Keep prompt DTOs, graph state, HTTP bodies, persisted data, and model output JSON-compatible. `LLM_INPUT_FORMAT=json` is the v1 default.
- Install the OpenAPI generator and TypeScript together as pinned development dependencies. Generate both dashboard and extension client bindings from the FastAPI schema; do not hand-maintain their route payload types.
- Keep real-provider validation manually gated, minimal, and free of prompt text, raw responses, credentials, and provider request identifiers in output.

## Follow-Up Trigger

Reopen this decision before changing the Python or Node support range, upgrading any accepted direct dependency, replacing the DeepSeek integration, retiring either V4 model, changing JSON Output behavior, or reconsidering TOON. A TOON proposal must pass the official fixture set, Merida adversarial encoder cases, and controlled real-provider comparison before it can replace JSON in real mode.
