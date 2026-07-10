# Make the Merida final app implementation-ready

Label: wayfinder:map

## Destination

Produce a coherent, decision-complete implementation specification and dependency-ordered migration roadmap for replacing the working Merida prototype with the proposed FastAPI, React `/dashboard`, and React Chrome extension app. The result must be ready to turn into implementation tickets while preserving existing Notion data, proven workflow outcomes, and evidence guardrails.

## Notes

- This is a planning effort. Ticket resolution may update glossaries, ADRs, and `docs/proposed-final-app/` to record settled decisions, but it must not implement the final app.
- The current Node backend, browser extension, and separate Python fit runtime remain runnable as the executable behavioral reference until parity-based cutover.
- Preserve domain outcomes, evidence guardrails, Notion effects, idempotency, and cleanup behavior; the prototype's HTML pages, route names, streaming transport, and internal module layout are not compatibility requirements.
- `Application` is the canonical pursuit record. `Job Posting` is its captured source opportunity and content. V1 keeps them one-to-one.
- Existing Notion databases, records, property names, and relations remain unchanged. A Notion adapter translates their physical legacy names into the canonical domain model.
- The React web surface is one `/dashboard` LLM process console. Capture stays in the React Chrome side panel. Editing and record management stay in Notion.
- Queues remain eligible-only. Application Analysis is bounded and sequential; Resume Creation remains one-at-a-time.
- Real mode remains local-first. Demo mode must exercise the same public module and API contracts without private Notion or DeepSeek credentials.
- Treat `routes.md`, `frontend.md`, `extension.md`, `notion-schema.md`, and `ai-workflows.md` as the reviewed baseline. Older separate-page, streamed-response, and `/api/job-postings/*` references are known drift to reconcile after the relevant decisions settle.
- Every ticket session must consult `/wayfinder`. Grilling tickets also use `/grilling` and `/domain-modeling`; seam and interface decisions use `/codebase-design`; prototype tickets use `/prototype`; external fact-finding uses `/research`.
- Resolve no more than one ticket per session. Claim a ticket before work by changing its status from `open` to `claimed`.

## Decisions so far

- [Inventory the prototype behaviors that define migration parity](issues/01-inventory-prototype-parity-contract.md) — Versioned parity now protects workflow outcomes, evidence guardrails, semantic Notion effects, idempotency, artifacts, and cleanup while explicitly superseding legacy UI, transport, runtime, template, and local-path details.
- [Validate the external AI and runtime dependency assumptions](issues/02-validate-external-ai-runtime-assumptions.md) — FastAPI, Pydantic, LangGraph, DeepSeek V4, and generated OpenAPI clients have a compatible, pinned candidate baseline; JSON is the v1 prompt format because no Python TOON implementation currently passes Merida's acceptance bar.

## Not yet specified

- The final structure and authority rules for the proposed documentation set, including the exact reconciliation edits, will become clear after the module, API, runtime, demo, and migration decisions settle.
- Distribution, installation, supported-platform, and release ergonomics remain fog until the target runtime and repository topology are chosen.
- CI gates, operational runbooks, and portfolio presentation assets remain fog until parity, recovery, and demo acceptance contracts are known.
- The final implementation-ticket and commit breakdown remains fog until the migration roadmap identifies its vertical slices and cutover gates.
- Prototype retirement, archival, and any post-cutover cleanup remain fog until the cutover roadmap is resolved.

## Out of scope

- Implementing the FastAPI backend, React dashboard, React extension, LangGraph workflows, adapters, or migration in this Wayfinder effort.
- Renaming or migrating existing Notion databases, properties, relations, or records.
- Building application, resume, or note editing and management into the dashboard; Notion remains that surface.
- Cloud hosting, multi-user accounts, remote authentication, tenancy, or SaaS operation for v1.
- A general chat agent, autonomous planner, multi-agent runtime, multi-provider LLM platform, or frontend model picker.
- Automated job application submission, email automation, interviewing, or recruiting CRM features.
- Batch Resume Creation, missing-PDF repair, or general-purpose Notes behavior in v1.
- Durable graph checkpoint storage, human interruption inside graph runs, or automated crash resumption in v1.
