# Choose the target runtime and repository topology

Type: grilling
Labels: ready-for-agent
Status: resolved
Blocked by: 02, 04
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

What exact Python and TypeScript workspace, package, build, generated-code, configuration, process-lifecycle, local-data, and developer-command topology should support FastAPI, the React dashboard, the React extension, shared UI, and demo mode while the frozen prototype remains runnable alongside it?

## Problem Statement

Merida now has a compatible FastAPI, Pydantic, LangGraph, DeepSeek, React, Vite, TypeScript, and OpenAPI-client baseline and has settled the target module seams. It does not yet have one authoritative repository and runtime topology that explains how those parts install, build, run, share code, generate contracts, persist local data, and coexist with the frozen Node prototype during migration.

Without that decision, implementation can drift into multiple JavaScript lockfiles, an implicit Python environment, duplicated API types, shared packages that bypass feature ownership, generated files that are stale or unreviewable, frontend processes that are required in production, local state mixed with fixtures, and root commands that silently stop running the prototype. That would make parity work harder to reproduce and could let demo mode pass through a different runtime shape than real mode.

## Solution

Use one private polyglot monorepo with root-level developer orchestration. The TypeScript side is one npm workspace containing the React dashboard, React Chrome extension, generated API client, and deliberately small shared UI and tooling packages. It has one root lockfile. The Python side is one installable FastAPI application package with one project definition and one reproducible lockfile managed by `uv`. The selected local toolchain is Python 3.14.2 and Node 22 LTS or newer within the accepted Node 22 support floor; CI verifies the documented Python 3.10 through 3.14 compatibility range separately.

The FastAPI ASGI app and emitted OpenAPI document are the contract authority. A root generation command exports OpenAPI, regenerates the shared TypeScript client, formats it deterministically, and fails if generation changes committed contract artifacts during verification. Both React consumers import that client through thin consumer-owned adapters. They do not copy route types or import backend source.

Development uses separate FastAPI and Vite processes coordinated by a root command. A production-shaped local build uses one long-lived FastAPI process: it serves `/api/v1`, the built `/dashboard`, and PDF downloads, while the independently built MV3 extension is loaded into Chrome. Demo and real mode select adapters at the FastAPI composition root and otherwise use the same modules, API, generated client, and built frontend.

The frozen prototype remains physically and operationally separate. Its current `npm start` and `npm test` commands retain their meaning until the migration roadmap performs final cutover. New-app commands remain under the `final:*` namespace during coexistence, and neither runtime imports the other.

The single acceptance seam is the root `test:final` verification gate. From a clean locked install it validates the FastAPI ASGI/OpenAPI contract, generated-client freshness, Python workflow and adapter behavior, TypeScript type checking, consumer tests, and production builds for the dashboard and extension. Deployable-specific tests remain useful beneath that seam, but a topology change is accepted only when this one root gate passes without private credentials or network calls.

## User Stories

1. As a Merida maintainer, I want one repository for the backend, dashboard, extension, generated client, shared UI, and migration reference, so that one change can preserve their contracts atomically.
2. As a Merida maintainer, I want the Python and TypeScript dependency systems explicit rather than blended, so that each ecosystem uses its native package model without hiding ownership.
3. As a Merida maintainer, I want one TypeScript workspace lockfile, so that the dashboard, extension, client generator, and shared packages resolve the same dependency graph.
4. As a Merida maintainer, I want one locked Python application environment, so that FastAPI, Pydantic, LangGraph, DeepSeek integration, and test dependencies install reproducibly.
5. As a new contributor, I want the required Python, Node, npm, and `uv` versions documented and checked, so that setup failures are immediate and understandable.
6. As a new contributor, I want one root setup path, so that I do not have to discover independent install rituals in every deployable.
7. As a new contributor, I want one root verification command, so that I can prove the complete final-app workspace is healthy before changing it.
8. As a backend developer, I want the FastAPI application to be an installable Python package, so that imports and tests do not depend on an ad hoc working directory.
9. As a backend developer, I want one ASGI application factory and one thin executable entry point, so that tests and production startup compose the same application.
10. As a backend developer, I want settings and adapter selection resolved at the composition root, so that workflow modules do not read environment variables.
11. As a backend developer, I want Python dependency groups for runtime and development concerns, so that production installation does not require test tooling.
12. As a backend developer, I want Python direct dependencies pinned by a lockfile while package constraints remain readable, so that upgrades are deliberate and reproducible.
13. As a backend developer, I want the supported Python range tested independently of the preferred local version, so that compatibility claims are evidence-backed.
14. As a frontend developer, I want the dashboard to be an npm workspace package, so that its React and Vite dependencies are owned explicitly.
15. As an extension developer, I want the Chrome extension to be an npm workspace package, so that its MV3 build and tests are independent of the dashboard.
16. As a frontend developer, I want workspace dependencies to use local package links, so that shared client and UI changes are exercised without publishing packages.
17. As a frontend developer, I want TypeScript enabled for production application and shared-package source, so that the generated client contract reaches consumer code without an untyped gap.
18. As a frontend developer, I want a common strict compiler baseline with deployable-specific overrides, so that shared safety rules do not erase browser-specific needs.
19. As a frontend developer, I want one formatting and linting policy owned by the repository, so that workspace packages do not drift into incompatible style configurations.
20. As a dashboard author, I want only dashboard interaction code in the dashboard package, so that the extension does not become coupled to operator-page state.
21. As an extension author, I want Chrome APIs isolated inside the extension package, so that shared packages remain ordinary browser-compatible TypeScript.
22. As a UI author, I want the shared UI package limited to visual primitives and design tokens, so that it does not become a home for workflow rules.
23. As a UI author, I want dashboard and extension features to compose shared primitives locally, so that their distinct interaction models remain feature-owned.
24. As an API consumer, I want one generated client package for both React consumers, so that route and payload interpretation cannot diverge.
25. As an API consumer, I want consumer-owned wrappers around generated operations, so that auth, base URL, and product-result presentation remain appropriate to each caller.
26. As an API consumer, I want generated files treated as disposable outputs of one command, so that nobody hand-edits contract code.
27. As a reviewer, I want the emitted OpenAPI document and generated client source committed, so that public-contract changes are visible in review.
28. As a reviewer, I want generated artifacts checked for freshness in CI, so that committed code cannot lag behind FastAPI.
29. As a reviewer, I want compiled bundles, Python environments, caches, mutable demo state, and generated PDFs excluded from version control, so that reviews contain source and contract decisions rather than machine output.
30. As a backend implementer, I want Pydantic models to remain the HTTP schema authority, so that TypeScript packages never become a second public-contract source.
31. As a backend implementer, I want OpenAPI generation to load the ASGI app without starting a server, so that contract generation is deterministic and fast.
32. As a backend implementer, I want OpenAPI generation to avoid real Notion and DeepSeek initialization, so that it runs without credentials or network access.
33. As a developer, I want a root development command to coordinate the API and dashboard, so that the ordinary feedback loop starts predictably.
34. As an extension developer, I want a separate watch/build command for the MV3 output, so that Chrome can reload a real extension directory instead of depending on a web-only dev server.
35. As a developer, I want individually addressable API, dashboard, and extension commands, so that I can debug one deployable without starting everything.
36. As a developer, I want coordinated development processes to terminate together, so that failed or interrupted sessions do not leave stale servers behind.
37. As a developer, I want stable local host and port defaults with environment overrides, so that documentation and extension setup remain predictable.
38. As a local operator, I want the production-shaped app to require one long-lived FastAPI process, so that I do not need a separate frontend server after building.
39. As a local operator, I want `/dashboard` assets served by FastAPI, so that same-origin dashboard requests retain the agreed local trust boundary.
40. As a local operator, I want the MV3 extension emitted as an independent build artifact, so that it can be loaded and updated through Chrome's extension workflow.
41. As a local operator, I want a missing dashboard build reported clearly at startup or route access, so that a partially built checkout does not masquerade as a healthy app.
42. As a local operator, I want real and demo mode selected once at backend startup, so that a request cannot silently cross between private and fictional workspaces.
43. As a local operator, I want the active mode and safe model names available through read-only settings, so that runtime behavior is observable without exposing secrets.
44. As a privacy-conscious operator, I want `.env` read only by backend processes and root tooling that launches them, so that browser bundles cannot embed Notion or DeepSeek credentials.
45. As a privacy-conscious operator, I want only explicitly public build-time variables exposed to Vite, so that arbitrary environment values do not enter frontend bundles.
46. As an extension user, I want backend URL and capture token stored through extension settings, so that the unpacked extension can connect without bundling secrets.
47. As an extension user, I want Notion tokens, database IDs, model keys, prompts, and full Job Content excluded from persistent extension storage, so that the browser remains a narrow capture client.
48. As a demo viewer, I want checked-in fictional seed fixtures, so that a fresh checkout shows a meaningful workflow without private data.
49. As a demo viewer, I want demo writes stored in a separate mutable local state file, so that I can exercise real workflow transitions without modifying seed fixtures.
50. As a demo viewer, I want one reset action to recreate mutable state from immutable fixtures, so that every walkthrough can begin from the same state.
51. As a demo viewer, I want demo PDFs written through the same artifact interface and download route as real PDFs, so that the walkthrough exercises the production contract.
52. As a maintainer, I want local data roots resolved from an explicit backend setting rather than the shell's current directory, so that commands behave consistently from the repository root.
53. As a maintainer, I want runtime directories created safely on startup, so that a clean checkout does not require manual folder creation.
54. As a maintainer, I want mutable state updates to use atomic replacement, so that interruption does not leave demo mode with truncated JSON.
55. As a maintainer, I want local paths and filenames excluded from public API meanings except through opaque download URLs, so that repository layout does not become a client contract.
56. As a migration implementer, I want the frozen prototype to keep its current startup and test commands, so that it remains an executable parity oracle.
57. As a migration implementer, I want final-app commands namespaced during coexistence, so that running a familiar root command cannot accidentally change which implementation executes.
58. As a migration implementer, I want no imports or workspace dependencies between the frozen prototype and final app, so that workflow cutover remains explicit.
59. As a migration implementer, I want parity fixtures to be readable by both test suites without sharing runtime modules, so that behavioral comparison does not create architectural coupling.
60. As a migration implementer, I want prototype and final-app processes to use different default ports, so that both can be inspected during migration.
61. As a migration implementer, I want generated-client and build commands to use only the final-app ASGI contract, so that legacy Node routes cannot influence the new client.
62. As a test author, I want workflow-module tests to run against fake narrow interfaces, so that business behavior is independent of HTTP, Notion, and browser processes.
63. As a test author, I want adapter conformance suites shared between real and demo implementations at workflow-owned interfaces, so that mode fidelity is observable.
64. As a test author, I want ASGI public-contract tests to exercise routes without a bound TCP port, so that the highest backend seam remains fast and deterministic.
65. As a test author, I want generated-client consumer tests to exercise typed success, blocked, already-created, file, cursor, and error variants, so that client regeneration cannot collapse product outcomes.
66. As a test author, I want dashboard and extension tests to target interaction modules at their public interfaces, so that tests do not depend on component internals.
67. As a test author, I want production builds included in the root gate, so that passing unit tests cannot hide an invalid dashboard or MV3 bundle.
68. As a test author, I want the root gate to run without private credentials, network access, or a live browser, so that it remains suitable for CI and new contributors.
69. As a CI maintainer, I want locked installs enforced before verification, so that CI never updates dependency resolution implicitly.
70. As a CI maintainer, I want cache keys derived from the root npm and Python lockfiles, so that cached dependencies cannot survive a contract-changing upgrade.
71. As a CI maintainer, I want generated-contract drift to fail with a focused message, so that the remedy is regeneration rather than manual editing.
72. As a release maintainer, I want dashboard assets and the extension built from the same commit as the backend schema, so that a local release cannot combine incompatible artifacts.
73. As a release maintainer, I want deployable outputs distinguishable from checked-in source, so that packaging and cleanup are mechanical.
74. As a future maintainer, I want dependency upgrades isolated from topology changes, so that version compatibility can be re-evaluated without redesigning module ownership.
75. As a future maintainer, I want adding a second backend package or package manager to require a new architectural decision, so that the repository does not fragment casually.

## Implementation Decisions

### Repository and package ownership

- Use one private polyglot monorepo. The deployables are one FastAPI application, one React dashboard, and one React MV3 extension. Shared packages are one generated API client and one deliberately small UI-primitives package. Tooling configuration may be exposed as a workspace package only where a real consumer needs package resolution; otherwise it remains root-owned configuration.
- Keep domain and workflow behavior in the FastAPI application's feature modules established by the module-seam decision. Repository packages are distribution and build boundaries, not permission to move feature behavior into generic shared code.
- Keep the dashboard and extension as separate npm workspace packages with their own package manifests, Vite configurations, TypeScript project references, tests, and build outputs.
- Keep the generated API client and shared UI as private npm workspace packages. They are never published for v1. Workspace consumers use the workspace protocol and import only their documented public entry points.
- Do not create a general `shared`, `common`, or cross-language domain package. Python owns canonical workflow and HTTP models; TypeScript receives public HTTP models through generation. Small browser-only display helpers stay with the consumer unless both React deployables demonstrably use them.
- The shared UI package may own design tokens and stateless visual primitives such as buttons, inputs, status chips, progress rows, dialogs, and tables. It must not own queues, capture state, workflow outcomes, API calls, Chrome access, or Notion language.
- The frozen prototype remains outside the final-app workspace dependency graph. Final-app packages do not import prototype modules, and prototype modules do not import final-app packages.

### Toolchain and dependency authority

- Use Python 3.14.2 as the preferred and pinned local/CI runtime for the first implementation. The Python project declares compatibility with 3.10 through 3.14 because the accepted dependency baseline supports that range; CI uses a focused compatibility matrix to keep that claim truthful.
- Use Node 22 LTS as the documented support floor and default reproducible CI runtime. Newer Node releases may be used locally only while they satisfy the lockfile and the generator's Node 22-or-newer requirement.
- Use npm workspaces with one root `package-lock.json`. All TypeScript runtime, build, test, generator, lint, and formatting dependencies resolve through that lockfile. Nested npm, pnpm, Yarn, or Bun lockfiles are forbidden.
- Use `uv` for Python environment creation, locked resolution, and command execution. The FastAPI application owns one `pyproject.toml`; one committed `uv.lock` records the complete runtime and development resolution. Requirements exports may be generated for external tooling but are not dependency authorities.
- Pin direct versions that issue 02 accepted, including FastAPI, Pydantic, LangGraph, the DeepSeek integration, the OpenAPI generator, and TypeScript. Compatible transitive versions are fixed by the two lockfiles. Any upgrade re-runs the runtime compatibility and generated-contract checks.
- Separate Python runtime and development dependency groups. Tests, type checking, linting, and OpenAPI export helpers belong to development groups unless the running application imports them.
- Root tool-version declarations and setup checks fail early with a safe message when Python, Node, npm, or `uv` is outside the supported policy.

### FastAPI runtime topology

- Package the backend as one installable Python distribution with one importable ASGI app factory and one thin executable module. Tests, OpenAPI export, development startup, and production-shaped startup all construct the application through the same factory.
- The application factory accepts validated settings and adapter overrides. It selects real or demo composition once at startup and injects only workflow-owned ports into each module.
- Importing the ASGI application for tests or OpenAPI export must not bind a port, read private workspace content, initialize a live Notion client, call DeepSeek, or mutate demo state.
- In development, run FastAPI through Uvicorn with reload. In the production-shaped local runtime, run one Uvicorn process without reload. No Node server, Python child runtime, process manager, container platform, or background worker is required for v1.
- FastAPI serves the versioned API, built dashboard assets, dashboard history fallback, and PDF download responses. It does not serve or dynamically host the Chrome extension.
- Startup validates configuration syntax, local-directory writability, built-dashboard availability for production-shaped mode, and adapter-specific readiness. Workflow-specific external readiness remains represented through the public readiness contract rather than crashing unrelated demo or read-only behavior.
- Bounded Application Analysis stays sequential inside one request, and Resume Creation stays one-at-a-time. The topology introduces no queue daemon, task broker, scheduler, checkpoint service, or second backend process.

### TypeScript workspace and browser builds

- Convert production React and shared-package source to strict TypeScript during implementation. Plain JavaScript may remain only in the frozen prototype or in generated/static files whose tool contract requires it.
- Each deployable owns its browser entry point and Vite build. The dashboard emits browser assets for FastAPI to serve. The extension emits a loadable MV3 directory containing its manifest, background service worker, side-panel HTML, JavaScript, CSS, and static assets.
- Extension development uses a watch build into the same unpacked-extension directory Chrome loads. A Vite HTTP development server may support isolated UI work, but it is not the authoritative MV3 execution path.
- Use root-owned strict TypeScript, lint, and formatting defaults with small package-specific overrides for DOM, Chrome, test, or build contexts. Do not duplicate configuration wholesale across workspaces.
- Browser bundles may receive only explicitly public values. Backend URL and Capture token remain runtime extension settings; dashboard API access remains same-origin. No `VITE_` or equivalent build-time mechanism may expose backend credentials.
- Build outputs are disposable and ignored. A clean build replaces them rather than relying on a previous bundle.

### OpenAPI and generated-code lifecycle

- The FastAPI/Pydantic ASGI application is the sole public HTTP contract authority. The checked-in OpenAPI document is a generated review artifact, not an independently edited schema.
- One root command exports OpenAPI in a deterministic form, invokes the pinned generator, and formats the resulting TypeScript source. It generates one private client package used by both React consumers.
- Commit the canonical OpenAPI artifact, generator configuration, generated TypeScript source, and the small handwritten client-package facade. Do not commit compiled client bundles, source maps, dashboard assets, extension assets, or generator caches.
- Generated source is never hand-edited. Consumer-specific concerns such as same-origin configuration, Capture-token injection, error presentation, and download handling live in thin handwritten adapters owned by the dashboard or extension.
- Verification regenerates into the canonical locations and fails when tracked output differs. It then typechecks and builds both consumers against that exact output.
- OpenAPI export is deterministic with demo-safe injected adapters and no credentials, network calls, timestamps, absolute paths, or environment-specific server URLs in the schema.
- Contract generation and ordinary client calls never include automatic POST retries. The generated client preserves the typed product and technical outcomes settled in issue 05.

### Configuration and secrets

- Keep one documented root `.env` contract for backend settings during coexistence, with a committed `.env.example` containing safe placeholders and demo defaults. The real `.env` remains ignored.
- The backend settings model is the only environment-variable parser. Workflow modules, routers, integrations, dashboard code, shared UI, and generated client code receive typed values or explicit constructor arguments instead of reading process environment directly.
- `MERIDA_MODE` selects exactly `demo` or `real` at startup. Adapter choice is immutable for the life of the process; there is no request-level mode switch.
- Backend-only settings include Notion credentials and database identifiers, DeepSeek credentials and model identifiers, prompt format, Capture token, allowed extension origin, local data root, export root, host, and port.
- The dashboard reads safe operator settings from the public API and uses a same-origin API base in the production-shaped build. It never displays or receives Capture, Notion, or DeepSeek secrets.
- The extension persists only backend URL, Capture token, and non-secret display preferences in Chrome storage. Capture token injection remains confined to the extension's handwritten client adapter.
- Command-line environment overrides are permitted for local ports and paths, but documented defaults are repository-root-relative and resolved to absolute paths by backend settings before use.

### Local data and demo mode

- Separate immutable checked-in demo fixtures from mutable runtime state. Fixtures contain only fictional Applications, Job Content, Master Resume evidence, prior analysis, and artifact metadata needed for the accepted walkthrough.
- On first demo start or explicit reset, create the mutable demo state from the versioned fixture set. Reset never edits the fixtures.
- Persist demo state as human-inspectable JSON behind the demo implementation of the workflow-owned store interfaces. Use validated schema/version metadata and atomic write-then-replace so interruption cannot leave a partially written state file.
- Keep mutable demo state, generated PDFs, temporary files, logs, caches, environments, and build outputs ignored. Keep an empty-directory marker only where tooling requires the directory to exist in a checkout.
- Resolve the configured local data and export roots independently of the current working directory. Create required writable directories on startup and return typed readiness failures when that is impossible.
- Real and demo modes use the same PDF adapter contract and public download URLs. Their files may share the configured export root only when filenames are opaque and collisions cannot cross modes; otherwise mode-specific subdirectories are required.
- Public responses return artifact IDs and download URLs, never filesystem paths. Cleanup and reset operate only within validated Merida-owned data roots and refuse unsafe roots.
- Demo startup, reset, test, and build require no Notion token, DeepSeek key, network access, or private prototype data.

### Process lifecycle and coexistence

- During development, a root coordinator starts the reloadable FastAPI process and dashboard Vite process, prefixes their output, propagates failure, and terminates all children on interrupt. Extension watch is opt-in because Chrome reload remains a separate operator action.
- The production-shaped flow is build once, then start one FastAPI process. FastAPI serves the built dashboard and API; Chrome loads the independently built extension directory.
- Use distinct documented defaults for the final-app API/dashboard development servers, extension UI tooling, legacy Node backend, and legacy fit runtime so both implementations can run during parity investigation.
- Preserve `npm start` and `npm test` as the frozen prototype's authoritative lifecycle and parity commands until the migration roadmap's final cutover. Do not silently redirect them earlier.
- Use `final:*` for all new-app setup, generation, development, build, start, reset, lint, and focused-test commands during coexistence. Keep `test:final` as the complete final-app verification gate already used by current work.
- The command contract is:
  - `final:setup` performs locked npm and Python environment installation;
  - `final:generate` exports OpenAPI and regenerates the shared client;
  - `final:check-generated` proves generated artifacts are current;
  - `final:dev`, `final:api`, `final:web`, and `final:extension` provide coordinated and focused development loops;
  - `final:typecheck`, `final:lint`, and `final:test` provide focused static and test feedback;
  - `final:build` creates the production dashboard and MV3 outputs;
  - `final:start` runs the one-process production-shaped app;
  - `test:final` performs the clean, credential-free acceptance gate;
  - `start` and `test` keep running the prototype until cutover.
- Root commands are thin orchestration only. Deployable-specific commands remain declared in their owning packages, and the root never copies their implementation logic.
- No Docker, Compose, Make, shell-only bootstrap, global Python package installation, or globally installed npm CLI is required for v1. These may be added later only to solve a demonstrated distribution need.

### Source-control and authority rules

- Commit source, fixtures, manifests, project definitions, both lockfiles, OpenAPI, generated TypeScript source, and documentation. Ignore environments, caches, mutable local state, PDFs, logs, and compiled outputs.
- Keep one source of truth for each concern: Python dependencies in the Python project plus lockfile, TypeScript dependencies in workspace manifests plus root lockfile, HTTP contracts in FastAPI/Pydantic, generated browser types in the client package, runtime settings in the backend settings model, extension-local connection values in Chrome storage, and demo seed state in versioned fixtures.
- The topology decision does not change the domain seams, public routes, Notion compatibility rules, evidence guardrails, workflow sequencing, or product UI chosen by earlier issues.

## Testing Decisions

- A good topology test observes an external package, command, module, HTTP, adapter, or built-artifact contract. It does not assert directory enumeration, private helper calls, framework internals, generated formatting trivia, or the exact process-coordinator implementation.
- The highest and single acceptance seam is `test:final` after locked installation. It must run without `.env`, private credentials, network access, bound external services, or mutable state from a previous run.
- The acceptance gate verifies, in dependency order: deterministic OpenAPI export; generated-client freshness; Python unit and workflow tests; real/demo store conformance tests with fakes for external services; ASGI public-contract tests; TypeScript type checking; dashboard and extension interaction tests; and production builds for both browser consumers.
- ASGI tests are the highest backend seam. They construct the real app factory with demo or fake adapters and cover readiness, settings privacy, auth, validation, queues, typed workflow outcomes, idempotency, PDF responses, static dashboard serving, and safe errors without binding a TCP port.
- Workflow tests exercise `ApplicationCapture`, `ApplicationAnalysis`, and `ResumeCreation` through their public interfaces with narrow fake stores and model adapters. Existing public-contract and parity tests are prior art; migration work adds cases rather than replacing them with framework-level tests.
- Store conformance tests run the same behavioral cases against demo and Notion implementations of `CaptureStore`, `ApplicationAnalysisStore`, and `ResumeCreationStore`. The compatibility suite specified by issue 06 is the prior art and authority for physical Notion mapping tests.
- Generated-client tests compile representative dashboard and extension adapters and assert typed success, blocked, already-created, file, cursor-recovery, validation, auth, and technical-error variants. They do not snapshot the entire generated tree.
- Dashboard tests target its interaction/session seam: queue refresh and reset, sequential Analysis progress, retained final results, Resume artifact links, and typed error presentation. Component markup snapshots are not the topology acceptance surface.
- Extension tests target capture evidence, settings, capture-session, and client-adapter seams: token injection, review edits, dirty-form protection, retry preservation, duplicate results, and absence of secret persistence. A browser smoke walkthrough remains useful but is not required for the credential-free root gate.
- Build tests inspect only externally required outputs: dashboard entry assets exist and can be served, and the extension output contains a valid MV3 manifest plus referenced side-panel and background assets. Hashed filenames and bundle chunk layout are not asserted.
- Process smoke tests may start the production-shaped FastAPI process on an ephemeral port, verify health and `/dashboard`, and terminate it cleanly. They remain a separate CI or release check if process startup would make the normal gate materially slower or flaky.
- Compatibility CI runs the complete gate on the preferred Python 3.14.2 and Node 22 toolchain. A narrower matrix reruns Python tests and OpenAPI export on Python 3.10 through 3.14. Node versions newer than the support floor are informative until explicitly adopted.
- Locked-install CI fails if npm or `uv` would update a lockfile. Generated-contract CI fails if regeneration changes tracked OpenAPI or TypeScript source.
- Prototype `npm test` remains a separate parity gate throughout coexistence. `test:final` must not import or execute prototype runtime modules, though migration CI may run both commands sequentially as two independent proofs.

## Out of Scope

- Implementing or migrating the FastAPI workflows, React UI, Chrome extension, Notion adapter, DeepSeek adapter, PDF renderer, or parity fixtures.
- Choosing new feature seams, changing the public API, renaming existing Notion properties, or changing accepted Capture, Analysis, Resume Creation, evidence, idempotency, or cleanup behavior.
- Cloud deployment, containers, hosted databases, task queues, background workers, multi-process scaling, remote authentication, multi-user tenancy, or SaaS operation.
- Publishing Python or npm packages to public registries.
- Packaging a desktop application, native installer, Chrome Web Store release, standalone executable, or operating-system service.
- Replacing npm or `uv` with a generalized build system, monorepo task cache, Makefile, or container-only workflow.
- Requiring Docker, a live browser, Notion, DeepSeek, or private credentials for ordinary setup, builds, or the final-app acceptance gate.
- Retiring the prototype or changing the meaning of `npm start` and `npm test`; those actions belong to the dependency-ordered migration and cutover roadmap.
- Defining final demo fixture content and walkthrough acceptance beyond the topology required to store, reset, and execute it; issue 09 owns those details.
- Defining concurrency locks, idempotency records, crash recovery, and compensation semantics; issue 08 owns those details.

## Further Notes

- This decision deliberately favors a boring repository: one lockfile per language ecosystem, one backend process, one generated client, and one root acceptance command.
- The currently implemented demo vertical slice already approximates much of this shape. That code is evidence that the topology is viable, not permission to weaken the unresolved real-mode, demo-acceptance, recovery, or migration contracts.
- The documentation set should use the selected support floors consistently: Python 3.14.2 as the preferred pinned runtime with a tested 3.10 through 3.14 range, Node 22 LTS as the support floor, npm workspaces for TypeScript, and `uv` for Python locking and execution.
- If `uv` or the preferred Python version proves unavailable on a supported contributor platform, treat that as a topology decision failure to resolve explicitly; do not add an undocumented parallel pip setup path.
- Revisit this decision before adding another backend deployable, another JavaScript package manager, a second Python project, a background worker, a package registry release, or a cloud deployment target.
