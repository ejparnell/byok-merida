# Remove demo mode from the final app

Type: task
Labels: ready-for-agent
Status: resolved
Blocked by: 03, 05, 06, 07, 08
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

How should the proposed final app remove the already-built demo product mode while preserving credential-free automated verification and the real Notion and DeepSeek workflow contracts?

## Problem Statement

Merida's proposed final app currently treats demo mode as a second product runtime. It selects fictional workspace and model adapters at startup, persists mutable fixture state, generates demo artifacts, exposes mode and workspace distinctions through public responses, includes a demo-reset operation in OpenAPI and the generated client, and presents demo-specific controls in the dashboard. That implementation was useful for proving the FastAPI, React, extension, and generated-client vertical slice, but it is not part of the product the user wants to keep.

Retaining demo mode would make the final app support two compositions, two data lifecycles, demo-only public contract surface, reset concurrency, fixture privacy rules, and portfolio behavior that provide no ongoing user value. It would also allow the credential-free path to become the path tested most thoroughly while the only intended product path—real local operation against the user's existing Notion workspace and configured DeepSeek models—receives less direct acceptance coverage.

Merida still needs deterministic, credential-free tests. Those tests do not require a user-selectable demo mode. Test-only fakes can implement the existing workflow-owned store, model, PDF, journal, clock, and barrier interfaces without appearing in production settings, runtime composition, OpenAPI, generated clients, browser UI, or distributable assets.

## Solution

Ship one local-first final-app runtime composed with the real Notion compatibility adapter, real task-specific DeepSeek adapters, the real PDF adapter, and the recovery journal. Remove demo as a product concept rather than renaming it, hiding its controls, or leaving it as a dormant configuration option.

The backend will no longer accept a mode selector, compose demo workspace or deterministic demo-model adapters, persist demo state, load demo fixtures, or expose demo reset. Public health and operator settings will describe readiness for the single real composition without `demo`/`real` or `demo`/`notion` discriminators. The dashboard and extension will consume that simplified contract and contain no demo labels, reset action, or demo-specific readiness branch. OpenAPI and the generated client will remove the demo-only operation and types.

Deterministic fakes remain available only to automated tests through explicit dependency injection. They exercise the same workflow modules and the same FastAPI ASGI/OpenAPI boundary as the real composition, but they are not selectable by environment variables or requests and are not shipped as a second workspace. OpenAPI export constructs the route schema without credentials or external calls; it does not need to boot a fictional product runtime.

The highest acceptance seam is the public FastAPI ASGI application and emitted OpenAPI document, exercised by both React consumers through the one generated client. Acceptance proves that the final product has one real composition and no demo surface while credential-free tests still cover workflow outcomes through injected fakes.

## User Stories

1. As the Merida operator, I want one runtime behavior, so that I never have to determine whether I am looking at fictional or real records.
2. As the Merida operator, I want startup to target my configured Notion workspace, so that successful readiness means the app can perform real work.
3. As the Merida operator, I want configured DeepSeek models used for Analysis and Resume Creation, so that displayed model information describes the actual workflows.
4. As the Merida operator, I want missing real credentials reported as blocked readiness, so that the app never silently falls back to fictional data.
5. As the Merida operator, I want missing or incompatible Notion schema reported explicitly, so that demo behavior cannot mask a workspace problem.
6. As the Merida operator, I want no demo reset action, so that there is no product control capable of replacing application state with fixtures.
7. As the Merida operator, I want no demo badge or mode chip, so that the dashboard communicates operational state rather than a discarded runtime choice.
8. As the Merida operator, I want health responses to describe real dependencies directly, so that readiness is concise and unambiguous.
9. As the Merida operator, I want operator settings to omit a meaningless mode value, so that every returned field helps operate the final app.
10. As the Merida operator, I want PDF downloads to refer only to real workflow artifacts, so that no fictional exports accumulate beside my work.
11. As an extension user, I want capture readiness to depend on the real backend and Notion workspace, so that a green state guarantees Capture can persist reviewed data.
12. As an extension user, I want no demo-specific readiness shortcut, so that the side panel cannot claim readiness while real integrations are unavailable.
13. As an extension user, I want review-first Fill Form and Create in Notion behavior preserved, so that removing demo mode does not change the accepted Capture interaction.
14. As a dashboard user, I want the eligible-only Analysis and Resume queues preserved, so that removing demo mode does not broaden the operator surface.
15. As a dashboard user, I want Analysis and Resume results to retain their typed outcomes, so that removing demo mode does not weaken workflow feedback.
16. As a dashboard user, I want Notion to remain the record-management surface, so that demo removal does not introduce editing controls into the dashboard.
17. As an API consumer, I want demo reset absent from OpenAPI, so that the generated client exposes only supported product operations.
18. As an API consumer, I want the demo-only error code removed, so that impossible runtime states are not part of every client's error union.
19. As an API consumer, I want mode and workspace discriminators removed where only one value remains, so that the contract does not preserve false variability.
20. As an API consumer, I want existing Capture, Analysis, Resume, PDF, health, settings, auth, and pagination contracts otherwise preserved, so that demo removal remains a focused contract change.
21. As a backend maintainer, I want one production composition root, so that adapter selection cannot drift between fictional and real workflows.
22. As a backend maintainer, I want the mode environment setting removed, so that an obsolete value cannot change product behavior.
23. As a backend maintainer, I want demo fixture and state settings removed, so that runtime configuration contains no dead product concepts.
24. As a backend maintainer, I want demo workspace and deterministic demo model implementations removed from production source, so that only supported integrations ship.
25. As a backend maintainer, I want demo reset exclusion removed from the execution coordinator, so that concurrency rules describe real mutations only.
26. As a backend maintainer, I want Capture, Analysis, and Resume exclusion and recovery rules preserved, so that demo cleanup does not weaken safety.
27. As a backend maintainer, I want real adapters injected through the existing workflow-owned interfaces, so that demo removal does not collapse deep module seams.
28. As a backend maintainer, I want OpenAPI export to avoid provider initialization and network calls, so that contract generation remains deterministic without a demo runtime.
29. As a backend maintainer, I want startup to fail or report blocked readiness rather than substitute fakes, so that configuration errors remain truthful.
30. As a test author, I want explicit fake stores and models available to tests, so that workflow behavior remains deterministic and credential-free.
31. As a test author, I want test fakes injected directly into the application factory, so that they cannot be selected in a normal final-app process.
32. As a test author, I want public ASGI tests to exercise the real route and schema surface with fakes behind workflow interfaces, so that tests cover external behavior without creating a second product mode.
33. As a test author, I want store conformance tests shared by the fake and Notion implementations, so that fake success cannot conceal semantic adapter drift.
34. As a test author, I want model contract tests shared by deterministic fakes and DeepSeek adapters, so that evidence and output rules remain aligned.
35. As a test author, I want resettable test state owned by each test fixture, so that deterministic setup does not require a public reset endpoint.
36. As a test author, I want temporary PDF and journal storage isolated per test, so that tests do not write mutable state into the product data root.
37. As a reviewer, I want the generated OpenAPI and TypeScript client checked after demo removal, so that no demo operation or type survives accidentally.
38. As a reviewer, I want browser production builds checked for demo text and controls, so that dormant UI branches are not shipped.
39. As a reviewer, I want credential-free verification to remain the root gate, so that removing the demo product does not require live services for ordinary development.
40. As a reviewer, I want a separate opt-in real-integration smoke check, so that Notion and DeepSeek configuration is validated without making CI depend on private credentials.
41. As a migration implementer, I want demo code treated as disposable scaffolding, so that it is removed rather than carried through final cutover.
42. As a migration implementer, I want completed demo work used as structural evidence only, so that useful module and client seams survive without preserving fictional behavior.
43. As a migration implementer, I want documentation reconciled to the one-runtime decision, so that setup and operations never instruct users to choose demo mode.
44. As a migration implementer, I want the frozen Node prototype to remain the real-workflow reference until real FastAPI parity passes, so that removing demo mode does not force premature cutover.
45. As a privacy-conscious operator, I want no checked-in portfolio dataset presented as application state, so that fictional and private work cannot be confused.
46. As a privacy-conscious operator, I want fake test values excluded from logs and shipped UI just like private values, so that test infrastructure stays invisible to product users.
47. As a maintainer, I want no replacement showcase, sample workspace, seed command, or hidden demo route added under another name, so that this removal remains durable.
48. As a maintainer, I want future test doubles evaluated as test infrastructure rather than product modes, so that deterministic verification does not recreate this split.

## Implementation Decisions

### Product runtime and composition

- The final app has exactly one product composition: the real Notion compatibility adapter, real task-specific DeepSeek adapters, real PDF artifact adapter, and local recovery journal behind the settled workflow-owned interfaces.
- Remove startup adapter selection. There is no environment, command-line, request, cookie, query, browser-storage, or UI mechanism that selects a fictional workspace or deterministic product model.
- Remove the mode configuration value and all demo fixture and mutable-state configuration. Invalid legacy mode variables are ignored only if the settings library already ignores unknown variables; they never influence behavior.
- Missing credentials, unreachable providers, or incompatible Notion schema produce the existing safe readiness and workflow-blocked outcomes. The application never falls back to fake data or deterministic model results.
- Production application construction does not import, instantiate, or conditionally reference fake stores or fake models. Tests may call an explicit dependency-injection factory that is unavailable as an operator setting.
- The accepted workflow module boundaries remain unchanged. Removing one set of adapters is not permission to merge Notion, DeepSeek, PDF, recovery, or HTTP details into workflow modules.

### Public API and generated client

- Remove the demo administration operation from the route inventory and emitted OpenAPI document. Requests to its former URL follow the ordinary unmatched-route behavior; there is no special inactive-demo response.
- Remove the demo-only technical error code and reset response schema from the public error and response unions.
- Remove `mode` from general health and operator-settings responses. Remove the demo-versus-Notion workspace discriminator from Notion health and operator settings; either omit `workspace` or return stable useful Notion identification that does not encode a variant. Prefer omission unless a real operator need is demonstrated.
- Operator settings continue to return safe configured-state booleans and read-only model names. They never return credentials, database identifiers, prompts, or private content.
- Preserve the settled `/api/v1` namespace and all non-demo operation IDs, request models, typed product outcomes, technical envelopes, Capture-token policy, CORS policy, cursor behavior, and download contract.
- Regenerate the canonical OpenAPI artifact and shared TypeScript client after the backend contract changes. Remove reset exports, reset types, obsolete discriminated unions, and any handwritten adapter method that exists only for demo administration.
- OpenAPI export constructs the ASGI schema without performing Notion or DeepSeek I/O. It may inject inert test dependencies for construction only, but those dependencies cannot alter the emitted product surface or become a runtime fallback.

### Dashboard and extension

- Remove the dashboard mode indicator, demo reset control, demo-only pending state, demo-specific explanatory copy, and reset client method.
- Preserve the dashboard's process-console role, model display, eligible-only queues, bounded Analysis execution, one-at-a-time Resume Creation, retained outputs, and links to Notion and PDF artifacts.
- Remove the extension's demo readiness shortcut. Capture readiness requires the real backend settings and Notion checks already defined by the public health contract.
- Preserve review-first Capture, dirty-form protection, source-page provenance, `Fill Form`, `Create in Notion`, `Review required`, and `Application already captured` behavior.
- Demo-looking example URLs used solely as isolated test input may remain when they are clearly test fixtures and are not shown in production. Rename them to neutral example values when that makes their test-only role clearer.

### Data, artifacts, concurrency, and recovery

- Remove checked-in product demo fixtures, mutable demo state, demo state migration/version logic, demo reset behavior, and demo-specific artifact metadata. Do not replace them with a seed, sample, showcase, preview, sandbox, or portfolio mode.
- Preserve the real export root, opaque PDF identifiers, atomic PDF publication, path validation, and cleanup rules.
- Remove the demo-reset global exclusion key, reset gate, and reset-related conflict tests from the execution coordinator. Preserve workflow gates, canonical-URL Capture exclusion, per-Application exclusion, one-worker enforcement, effect journaling, compensation, and restart reconciliation.
- Recovery state remains content-free and real-workflow-owned. Removal of demo persistence does not remove or relax the effect journal.
- Existing fictional data already written only to the ignored demo state or demo export area may be deleted during implementation. No cleanup operation may search, mutate, or archive records in the real Notion workspace based on demo titles or fixture identifiers.

### Test infrastructure and verification

- Retain deterministic in-memory or temporary-disk fakes for workflow stores, task-specific models, PDF artifacts, journals, clocks, and concurrency barriers. Name and locate them as test support, not production integrations.
- Test fakes implement the same narrow workflow-owned interfaces and semantic conformance suites as real adapters where equivalence matters. They need not imitate provider transport details or expose a reset operation through HTTP.
- Every test creates its own initial state directly through fixture construction. Tests that need restart coverage reconstruct the application against the same test-owned durable fake state and journal.
- Credential-free root verification remains mandatory. It performs no live Notion or DeepSeek requests and uses no private data, while still testing routes, workflow outcomes, effect order, cleanup, recovery, OpenAPI generation, generated-client freshness, TypeScript types, and both React builds.
- Live Notion and DeepSeek verification remains an explicit local smoke procedure outside the ordinary root gate. Real mode cannot be declared cut over until that smoke check and the accepted parity suites pass.

### Documentation and decision reconciliation

- Reconcile proposed-final-app architecture, workflows, routes, frontend, extension, codebase structure, migration, setup, operations, and environment documentation to one real runtime.
- Earlier decisions that require shared workflow interfaces, credential-free tests, OpenAPI generation, generated-client freshness, local data safety, recovery, and parity remain authoritative.
- Earlier statements that require a demo product mode, mode selection, demo persistence, demo fixtures, demo reset, demo-reset exclusion, demo portfolio behavior, or consumer behavior shared with demo are superseded by this issue.
- The already-built demo vertical slice remains evidence that the chosen ASGI, OpenAPI, generated-client, dashboard, extension, and workflow seams work together. It is scaffolding to remove, not a supported migration slice.

## Testing Decisions

- A good test asserts public behavior: HTTP status and typed response, emitted OpenAPI, generated-client surface, visible dashboard or extension state, semantic fake-workspace effects, published artifact behavior, and recovery results. It does not assert private composition helpers, concrete fake classes, source-file absence by exact path, or internal call counts unless an effect boundary requires it.
- The single highest acceptance seam is the FastAPI ASGI application and emitted OpenAPI document, with deterministic test dependencies injected behind the same workflow interfaces used by the real composition. Both React consumers compile and run their consumer tests against the one regenerated client.
- Public contract tests prove the former demo-reset URL is not an operation, the demo-only error and response schemas are absent, health and operator settings contain no mode discriminator, and all non-demo operation IDs and typed outcomes remain available.
- Composition tests prove ordinary startup selects only real adapters, missing real configuration blocks safely, and no environment or request value can select test fakes.
- Dashboard tests prove no mode badge, demo copy, or reset control is rendered and that normal queue, run, result, model-display, and artifact interactions still work.
- Extension tests prove readiness has no demo bypass and that review-first prepare and confirm behavior still uses the Capture token and real readiness contract.
- Workflow tests retain existing Capture canonical-URL idempotency, Analysis body-first/property-second repair, Resume relation-last commit, evidence guardrails, compensation, and restart recovery scenarios through deterministic fakes.
- Adapter conformance tests run the same semantic store assertions against test fakes and deterministic Notion transport recordings. Model contract tests compare deterministic fake outputs and recorded DeepSeek responses against the same evidence and schema requirements.
- Concurrency tests remove reset-specific cases but retain overlapping Analysis, Resume, Capture, per-Application exclusion, cancellation release, fixed lock ordering, and fail-fast conflict behavior.
- Data tests prove ordinary product startup does not create demo fixture or mutable-state files. Test persistence and generated artifacts remain isolated in temporary roots.
- Static contract checks search emitted OpenAPI, generated client exports, production browser bundles, and operator-facing copy for obsolete demo administration concepts. Neutral test fixture values are not failures merely because they are fictional.
- Existing prior art includes ASGI public-contract tests, generated-client adapter tests, dashboard session tests, extension Capture tests, store conformance helpers, deterministic Notion transport recordings, effect-order tests, and restart recovery tests.
- Completion requires the root final-app verification gate to pass without credentials or network calls. Before real cutover, a separate manual smoke run verifies Notion readiness, one safe Capture path, bounded model connectivity, and artifact access against the configured real environment.

## Out of Scope

- Adding a replacement sample, showcase, seed, sandbox, preview, trial, tutorial, offline, portfolio, or mock product mode.
- Keeping a hidden reset route, dormant mode selector, undocumented fixture loader, or production fallback to deterministic adapters.
- Removing deterministic test doubles, credential-free automated tests, test-owned fixtures, transport recordings, fault injection, or temporary test persistence.
- Changing Application Status values, eligible-only queue rules, cursor semantics, Analysis batching, Resume one-at-a-time behavior, evidence guardrails, scoring, prompts, output schemas, effect ordering, compensation, or recovery policy.
- Renaming or migrating existing Notion databases, properties, relations, records, or body-section compatibility rules.
- Adding record editing, schema repair, recovery controls, model selection, or configuration editing to the dashboard or extension.
- Cloud hosting, multi-user operation, remote authentication, tenancy, multiple workers, background jobs, or distributed coordination.
- Retiring the Node prototype before the real FastAPI workflows meet their parity and cutover gates.
- Implementing the removal in this planning ticket; the migration roadmap will place the changes into dependency-ordered implementation slices.

## Further Notes

- This is a deliberate reversal of the earlier demo-first assumption. The user does not want demo mode in the final app, so simplicity and truthful real-runtime readiness take precedence over portfolio walkthrough behavior.
- The removal should be done as a vertical contract cleanup rather than a UI-only deletion. Leaving demo schemas, reset operations, composition branches, fixtures, or concurrency rules behind would preserve most of the maintenance burden.
- Test-only fakes are not demo mode. Their defining properties are explicit injection, test ownership, isolation, no operator selection, no shipped control surface, and no claim to be an alternate product workspace.
- If a future proposal needs a public sample experience, it requires a new product decision and must not reactivate this code implicitly.
