# Merida Final-App Dead-Code Audit

- Date: 2026-07-12
- Revision audited: `b9874337d098118ac4075798036c3a6954005b07`
- Requested end state: one supported FastAPI/React application, with no old implementation left in the working tree

## Implementation update

The requested retirement was implemented on 2026-07-12 after this baseline audit:

- the FastAPI/React application is now the only supported runtime;
- `npm start` and `npm test` are the default lifecycle and acceptance commands;
- the final parity corpus lives under `apps/api/tests/fixtures/`;
- the old `src/` runtime, handwritten extension, sidecar, executable parity harness, throwaway visual prototypes, migration scratch tree, and old operator docs were removed;
- current documentation now lives directly under `docs/`;
- `scripts/check-final-only.mjs` prevents legacy runtime paths and lifecycle names from returning.

The remainder of this report preserves the pre-removal findings and evidence that defined the cleanup scope.

## Executive verdict

The repository is **not final-only yet**.

The final FastAPI API, React dashboard, React MV3 extension, generated API client, and shared UI package form a clean, independent application. Their complete acceptance gate passes. No substantive final-app module, API route, workspace package, direct dependency, CSS selector, keyframe, or CSS variable is orphaned.

The largest old implementation is not technically dead, however. The 136 tracked files under `src/` are still wired to the repository's default `start` and `test` commands. The migration plan intentionally kept that implementation runnable as a fallback until real-provider smoke acceptance, default-command cutover, and an observation window were complete. The latest recorded audit says no mutating real-provider smoke was run, so there is no completed cutover record.

To reach the requested end state, Merida needs a deliberate **prototype-retirement change**, not only scattered dead-symbol deletion. That change should:

1. move the one parity fixture still consumed by the final tests;
2. make the final app the default runtime and test target;
3. replace the prototype operator documentation;
4. delete the complete old runtime, its tests, extension, sidecar, and throwaway UI studies;
5. remove the smaller dead paths found inside the final implementation;
6. rerun the final gate from a clean checkout.

## Audit classifications

- **Confirmed dead**: no production, test, build, tool, or documented operator entry point consumes it.
- **Obsolete but still wired**: old implementation that the repository can still start or test. It is removal scope for a final-only repository, but it must first be unwired.
- **Test-only production surface**: code placed in production only to arrange tests; replace the test setup before removal.
- **Unreachable but required**: a desired behavior whose current state transition cannot be observed reliably. Fix it rather than deleting it.
- **Generated or operational**: reproducible build output, generated contract code, test fakes, or compatibility behavior that is still intentional. Do not classify it as dead.

## Verification performed

The following passed at the audited revision:

- `npm run test:final`
- generated OpenAPI/client freshness
- final TypeScript type checking and ESLint/Prettier checks
- TypeScript `noUnusedLocals` and `noUnusedParameters` compiler checks
- 18 dashboard/extension tests
- 151 FastAPI/Python tests
- API client, dashboard, and extension production builds
- no-demo source and build scans

Static tracing covered root scripts, npm workspaces, browser entry points, the FastAPI composition root and CLI, Python imports, final TypeScript imports/exports, CSS selectors, tracked files, ignored local artifacts, and prototype parity references. The worktree was clean before the report was added and remained free of generated drift after the final gate.

## Final application boundary to keep

These paths are active final-app code or required final-app support:

- `apps/api/`
- `apps/web/`
- `apps/extension/`
- `packages/api-client/`
- `packages/ui/`
- `scripts/final-dev.mjs`
- `scripts/final-python.mjs`
- `scripts/final-setup.mjs`
- `scripts/check-no-demo-surface.mjs`
- `openapi-ts.config.mjs`
- `tsconfig.base.json` and `tsconfig.final.json`
- `app-data/export/` and `app-data/recovery/` as runtime locations

The tracked OpenAPI document and generated client are freshness-gated contract artifacts. Do not manually prune individual generated SDK operations or helper files just because one current UI does not call them. The ignored `apps/web/dist/`, `apps/extension/dist/`, and `packages/api-client/dist/` directories are current reproducible outputs, not legacy source.

## Finding 1: the entire old app remains live through root commands

- Severity: **final-only blocker**
- Classification: **obsolete but still wired**

[package.json](../package.json#L16) still assigns the default commands to the old implementation:

- `start` -> `src/backend/start.js`
- `start:node` -> `src/backend/server.js`
- `start:fit-runtime` -> `src/features/resumes/ml/server.py`
- `setup:ml` -> the root `.venv` and old ML requirements
- `test` -> prototype Node, parity, and Python-sidecar tests

The old tree contains 136 tracked files and roughly 12,754 lines of JavaScript/Python implementation and test code:

| Group                                       | Files | Removal scope                                                                  |
| ------------------------------------------- | ----: | ------------------------------------------------------------------------------ |
| Old runtime                                 |    44 | `src/backend/`, feature backends/libs/types, old Python ML sidecar, `src/lib/` |
| Handwritten old extension                   |    12 | `src/features/jobPostings/extension/`                                          |
| Old implementation tests                    |    25 | `src/**/test/` and `src/backend/test/`                                         |
| Prototype docs, glossaries, plans, and ADRs |    55 | documentation currently colocated under `src/`                                 |

No final app source imports any module under `src/`. Its only consumers are the legacy root lifecycle commands and the prototype parity observers. Once those consumers are replaced, delete the whole directory as one unit:

```text
src/
  backend/
  features/jobPostings/
  features/notes/
  features/resumes/
  lib/
```

Deleting only selected files inside `src/` would leave two partial applications and make the repository harder to reason about.

### Current retirement-policy conflict

The accepted roadmap said default cutover happens before deletion and prototype retirement follows an observation window. The baseline evidence lived at `.scratch/proposed-final-app/issues/10-build-migration-roadmap.md`, `docs/proposed-final-app/migration-plan.md`, `docs/proposed-final-app/operations.md`, and `report/final-app-feature-audit-20260711.md`; those migration-only files were removed with the old app. The feature audit recorded a green configured read-only runtime but no selected eligible Application for a mutating smoke path.

There are two coherent ways to authorize deletion:

1. complete the bounded real Capture -> Analysis -> Resume Creation smoke, record cutover evidence, make the final app default, observe it, then retire the prototype; or
2. explicitly waive the remaining smoke/observation policy and accept restore-from-Git as the only fallback.

The user's stated desire for a final-only repository supports the second direction, but this audit does not silently waive the existing safety policy.

## Finding 2: final tests still depend on one old parity fixture

- Severity: **deletion blocker**
- Classification: **live regression evidence in the wrong ownership tree**

[test_final_behavior_contract.py](../apps/api/tests/test_final_behavior_contract.py#L1) originally read:

```text
test/parity/fixtures/prototype-parity.v1.json
```

Therefore `test/parity/` cannot be deleted wholesale yet.

Before deleting it:

1. move the frozen JSON corpus into `apps/api/tests/fixtures/` under a final-owned name;
2. update `_fixtures()` in `test_target_parity_manifest.py`;
3. make the target fixture metadata describe the final regression authority rather than an executable prototype oracle;
4. run `npm run test:final`;
5. delete the old executable parity code:

```text
test/parity/observers/
test/parity/prototypeHarness.js
test/parity/prototypeParity.test.js
test/parity/parityContract.js
test/parity/parityContract.test.js
test/parity/README.md
```

The final target harness already invokes final-app regressions for every required fixture ID. The old observers and harness execute `src/` directly and have no place in a final-only application after the fixture is relocated.

### Parity coverage gap

The target test projects `CAPTURE-EVIDENCE-001` into Python values; it does not execute the final TypeScript collector. The frozen fixture also contains a 300,000-character visible-text case while the final collector/API enforce lower per-field and combined limits. The fixture should be reconciled with the final capture limits and exercised by `activeTabEvidence.test.ts`, or its claim should be narrowed. This is a test-authority gap, not permission to delete the final collector.

## Finding 3: confirmed dead Python code inside the final app

- Severity: **low**
- Classification: **confirmed dead**

### Unused prompt encoder protocol

[prompt_payload.py](../apps/api/merida_api/shared/prompt_payload.py#L19) defines `PromptPayloadEncoder`, but nothing imports or types against it. Production adapters use `JsonPromptPayloadEncoder` directly.

Remove `PromptPayloadEncoder` and its now-unneeded `Protocol` import. If encoder substitution is meant to remain a real seam, type the adapters against the protocol instead; do not leave an unused interface beside a concrete-only implementation.

### Unused Resume builder imports

[resume_builder.py](../apps/api/merida_api/features/resumes/resume_builder.py#L16) imports these aliases without using them:

- `PromptCategoryCoverage as _PromptCategoryCoverage`
- `PromptRequirement as _PromptRequirement`

The underlying Pydantic models remain live through `ResumeDraftInput`; remove only the two unused imports.

### Unexecuted target parity metadata

The historical `apps/api/tests/fixtures/target-parity.v1.json` was not loaded by any source or test. The final behavior harness hardcoded its projection policy and read the old JSON corpus directly.

Preferred cleanup: replace this stub with the relocated full final-owned corpus or make the test load a consolidated manifest. Otherwise delete it so a reviewer is not misled into thinking it is executable.

## Finding 4: production PDF helper exists only for test arrangement

- Severity: **low**
- Classification: **test-only production surface**

`ResumePdfArtifacts.save` in [ports.py](../apps/api/merida_api/features/resumes/ports.py#L200) and `LocalPdfArtifacts.save` in [pdf_export.py](../apps/api/merida_api/integrations/pdf_export.py#L128) have one caller: test setup in `test_execution_recovery.py`.

Runtime behavior uses the deeper `stage` -> `publish` -> `discard` boundary. Update the test to arrange its fixture through those operations, then remove `save` from the production protocol and adapter.

## Finding 5: confirmed dead extension/UI paths

- Severity: **low to medium**
- Classification: **confirmed dead or unwired**

### Dead field-ref plumbing

[App.tsx](../apps/extension/src/App.tsx#L1) imports `useRef` and `RefObject`, creates `firstField`, passes `fieldRef`, and attaches it to the Company Name input. Nothing reads or focuses that ref. The actual focus behavior queries the first missing field by name at [lines 449-454](../apps/extension/src/App.tsx#L449).

Remove the two imports, `firstField`, the `fieldRef` prop/type, the input `ref`, and the prop pass-through.

### Dead Idle disabled branch

`Idle` accepts an optional `disabled` property and binds it to the Fill Form button at [lines 146-170](../apps/extension/src/App.tsx#L146). Its sole render occurs only when Capture health is ready and never supplies the property. Remove the property, default, and button binding unless a real disabling state is added.

### Unused Capture session subscription API

`CaptureSession.subscribe()` is defined at [captureSession.ts lines 112-115](../apps/extension/src/session/captureSession.ts#L112) and exposed by the interface at line 212, but has no caller. The React app already supplies its callback to `createCaptureSession()`.

Remove `subscribe()` from the implementation and interface.

### Ignored `sourceChanged()` return value

`sourceChanged()` returns a boolean at [captureSession.ts lines 136-142](../apps/extension/src/session/captureSession.ts#L136), but its only caller ignores the result. The state mutation is live; the return channel is not. Change the method to return `void` and update the interface.

### Dead wrapper modifier classes

The extension emits `readiness is-ready|is-checking|is-blocked|is-offline` on the wrapper at [App.tsx line 484](../apps/extension/src/App.tsx#L484), but no CSS or script consumes those modifiers. The child `StatusDot` independently emits and uses its own live state class.

Use `className="readiness"`; this also removes the extension's only `cx` call and import.

The web app emits `theme-light` at [App.tsx line 517](../apps/web/src/App.tsx#L517), while CSS only needs the base `.app-shell` style and the `.theme-dark` override. Emit the dark modifier conditionally rather than generating an unused light token.

`StatusBadge` emits `is-${status}` on its wrapper at [packages/ui/src/index.tsx line 30](../packages/ui/src/index.tsx#L30), but CSS styles only `.status-badge` and the child `.status-dot.is-*`. Remove the unused wrapper modifier. The optional `StatusDot.status` and `StatusBadge.children` fallbacks also have no current caller; making those props required would narrow the final UI API, but this is optional cleanup rather than a correctness issue.

### Unwired Resume-result dismissal

`dismissResumeResult()` is exposed and implemented at [dashboardSession.ts lines 29-38 and 163-167](../apps/web/src/features/dashboard/dashboardSession.ts#L29), but no UI or test calls it.

This needs a product-contract decision rather than blind deletion: the accepted interaction design says result notices should be dismissible and temporary. Either wire a dismiss control/timer for Resume results and test it, or delete the method and update that acceptance statement.

## Finding 6: required Reading state is effectively unreachable

- Severity: **medium UX defect**
- Classification: **unreachable but required; fix, do not delete**

The extension collects active-tab evidence before calling `session.prepare()` at [App.tsx lines 393-400](../apps/extension/src/App.tsx#L393). Inside `prepare`, `captureSession.ts` publishes `reading` and immediately publishes `parsing` before the first await at [lines 68-75](../apps/extension/src/session/captureSession.ts#L68). React can batch both updates, so the `Reading current page` progress view does not cover evidence collection and may never render.

Move the Reading transition ahead of `collectCaptureEvidence()`, then transition to Parsing only when the API prepare request begins. Preserve the existing progress copy and add a state-transition test.

## Finding 7: disposable visual prototypes and local legacy residue

- Severity: **low**
- Classification: **confirmed retirement scope**

### Throwaway visual studies

These ignored local directories are not npm workspaces and are excluded from the final gate:

```text
apps/web-prototype/        approximately 3.0 MB
apps/extension-prototype/  approximately 1.6 MB
```

Both historical files, `apps/web-prototype/NOTES.md` and `apps/extension-prototype/NOTES.md`, said to throw the folder away after the direction was chosen. The direction is now implemented in `apps/web` and `apps/extension`.

Delete both directories, their `dist/` trees, the `prototype:frontend` and `prototype:extension` scripts, the `apps/*-prototype/` ignore rule, the redundant prototype ESLint ignore, and stale planning links that assume these ignored folders exist in a clean checkout.

### Unused root logo

`bownarrow.png` has no tracked caller and is byte-identical to the copy in the ignored web prototype. Delete it. If the final app should use the selected bow-and-arrow branding, first move a single canonical asset into the relevant final app's public assets and reference it explicitly.

### Old local environment and output

- Root `.venv/` is approximately 55 MB. Final scripts use `apps/api/.venv`; remove the root environment after deleting `setup:ml`.
- `export/Amplify-ElizabethParnell.pdf` is an ignored old-runtime output. Final PDFs live under `app-data/export`. Confirm the PDF is not personally needed before deleting it.
- `app-data/demo/` is an empty leftover from removed demo mode; delete it.
- `src/features/jobPostings/extension/local-config.js` is ignored old-extension state; delete it without copying secrets.

### Stale bytecode and caches

Ignored bytecode still includes names of deleted modules such as `demo_models`, `demo_workspace`, `deepseek_analysis`, and the former root `matching` module. Pytest caches still record removed demo tests. Clear those caches explicitly. Do not use a broad ignored-file clean command that would also erase the active `.env`, `apps/api/.venv`, final build outputs, or current runtime artifacts.

## Finding 8: current documentation and configuration still describe two apps

- Severity: **final-only blocker**
- Classification: **stale authority, not runtime code**

### Current operator docs

The root [README](../README.md#L1) is entirely the Node/sidecar prototype operator guide. It tells the operator to load the old handwritten extension, run `npm start`, use `/analysis` and `/resumes`, and write PDFs to `export/`.

The following are also prototype-current rather than final-current:

- `CONTEXT-MAP.md`
- `docs/architecture.md`
- `docs/workflows.md`
- `docs/notion-schema.md`
- `docs/operations.md`
- `docs/adr/0001-local-operator-backend-shell.md`

Promote and reconcile `docs/proposed-final-app/` as the single current documentation set. Remove `proposed` and coexistence wording, update the documented tree to the actual implementation, and either archive old design evidence under an unmistakable historical namespace or rely on Git history and remove it from the working tree. Leaving both sets in their current locations will continue to direct operators to the old app even after its code is deleted.

### Environment template

[.env.example](../.env.example#L1) mixes old and final settings. Remove these old-only variables:

- `PORT`
- `FIT_RUNTIME_PORT`
- `FIT_RUNTIME_URL`
- `PYTHON_BIN`
- `DEBUG_CAPTURE`
- `DEBUG_ANALYSIS_CONTENT`
- `DEEPSEEK_MODEL`

Retain the shared Notion/DeepSeek/Capture settings and the final `API_*`, `ANALYSIS_MODEL`, `RESUME_MODEL`, `EXPORT_PATH`, and `RECOVERY_JOURNAL_PATH` settings. Remove the `Proposed FastAPI + React app` label.

`LLM_INPUT_FORMAT` currently accepts only `json`; its non-JSON guard cannot be reached through typed settings. If final v1 intentionally has one input format, remove the setting, factory parameter, guard, and unused encoder protocol. If a future encoder selector is truly part of the maintained interface, keep the setting and type adapters against the protocol. Do not keep a speculative half-seam.

### Ignore and lint configuration

After retirement, remove legacy-specific entries for the throwaway prototype directories, old `export/`, and the old extension local config. Keep generic `.venv`, cache, generated-output, `app-data/export`, and `app-data/recovery` protections needed by the final app.

The final lint/format command omits the handwritten `packages/api-client/src/index.ts` and `operatorError.ts`; the final typecheck does include them. TypeScript tests are ignored by ESLint and excluded from `tsconfig.final.json`, although the test runner executes them. These are static-analysis blind spots rather than dead code. Add the handwritten client files and tests to the appropriate maintained lint/typecheck boundary during cleanup.

### Historical migration artifacts

`.scratch/proposed-final-app/` is resolved planning material, not runtime. It also contains a standalone Python conformance script with no current lifecycle command. The old `report/` architecture reviews and handoffs have no runtime role and point heavily into `src/`.

For a clean final-only working tree, move intentionally retained evidence to a clearly historical archive or remove it and rely on Git history. Keep the new `reports/` directory for current audits. Historical reports are not dead application code, but leaving them as current navigation surfaces will preserve ambiguity.

## Finding 9: code that looks old but must remain

Do not remove these items as part of dead-code cleanup:

- Legacy `Job Posting Analysis` body parsing/repair in the final Notion adapter. It reads existing user records and is covered by unchanged-workspace conformance tests.
- Test-only deterministic fakes under `apps/api/tests/fakes/`. They are injected through the final application factory and are exercised by the credential-free final gate.
- Empty Python `__init__.py` files. They are package scaffolding.
- `apps/api/merida_api/main.py`. The reloadable final API command uses `merida_api.main:app`.
- `apps/api/scripts/export_openapi.py`. The final client-generation command invokes it.
- Scoped health routes and the PDF route. They are registered, documented operator/API surfaces even when a React screen does not call them directly.
- `packages/ui/`. Both final React consumers import it.
- generated client support code and OpenAPI response variants.
- `apps/extension/public/background.js`. The MV3 manifest declares it as the service worker.

## Recommended deletion sequence

### Phase 1: remove confirmed dead and throwaway material

1. Remove the unused Python protocol/imports and dead UI/session plumbing.
2. Repair Reading progress and decide whether to wire Resume-result dismissal.
3. Delete ignored visual prototypes, root `bownarrow.png`, stale caches, empty demo data, and the root `.venv` after its old script is gone.
4. Replace or delete the unexecuted target parity metadata.

### Phase 2: establish one final-app authority

1. Move the frozen parity corpus into the final test fixture tree.
2. Make `npm start` run the final FastAPI application.
3. Make `npm test` run the final acceptance gate.
4. Remove old lifecycle/prototype scripts; simplify `final:*` names or retain only useful aliases.
5. Rewrite the root README, environment template, context map, and current operations docs for the final app.
6. Run both the updated final tests and a clean production build.

### Phase 3: retire the old implementation atomically

After completing the documented acceptance path or explicitly waiving it:

1. delete all of `src/`;
2. delete the executable prototype parity harness after relocating its fixture;
3. remove old docs/config references and legacy ignore rules;
4. archive or remove historical migration artifacts;
5. regenerate the lockfile if script/workspace changes require it;
6. verify that no active source or operator document references the deleted paths.

### Phase 4: final-only acceptance

Run from a clean checkout:

```sh
npm run final:setup
npm test
```

`final:setup` performs the locked npm install as part of clean setup.

Then verify:

- the built dashboard is served at `/dashboard`;
- the unpacked extension loads from `apps/extension/dist`;
- all 12 OpenAPI operations remain registered;
- generated client freshness passes;
- no `src/`, `test/parity` executable harness, `*-prototype`, `/analysis`, `/resumes`, old sidecar, or old extension path remains in current commands or operator docs;
- only `app-data/export` and `app-data/recovery` are used for final runtime artifacts;
- the Git worktree is clean after verification.

## Final conclusion

The rebuilt app itself is in good shape: the final runtime is complete, its gate is green, and there are no orphaned final modules or dependencies. The cleanup problem is mainly repository topology. Merida still treats the old application as a supported default and keeps two documentation authorities.

The correct cleanup is therefore an atomic retirement: preserve the one live parity corpus under final ownership, switch commands/docs, delete the whole old implementation, remove the small confirmed-dead paths listed above, and prove the resulting final-only tree with the existing acceptance gate.
