# Extension - Proposed

The proposed browser extension is a React Chrome Manifest V3 side panel for capturing Applications from job posting webpages. It is a focused capture surface, not a general Notion editor, not an Application Analysis interface, and not a Resume Creation interface.

The side panel has three responsibilities:

1. Check whether the local backend and capture configuration are ready.
2. Collect Capture Evidence from the active source page.
3. Let the user review and confirm an Application before it is written to Notion.

The React web dashboard remains responsible for Application Analysis and Resume Creation. Notion remains responsible for editing and managing Applications after capture.

## Extension Goals

- Keep the capture interface open beside the source page while the user reviews it.
- Make review-first capture the primary workflow.
- Collect enough readable Job Content for later Application Analysis and Resume Creation.
- Let the user correct important parsed fields before writing to Notion.
- Show whether capture created a new Application, found an existing Application, needs review, or failed.
- Keep Chrome APIs, page extraction, extension settings, and backend calls behind small extension modules.
- Avoid storing full private Job Content after the current side-panel session ends.
- Avoid exposing Notion credentials, database IDs, DeepSeek keys, prompts, or other backend secrets.

## Backend Routes Used By The Extension

| Route | Used for | Purpose |
| --- | --- | --- |
| `GET /health` | Side-panel readiness | Shows whether the local backend and Notion workspace are ready for capture. |
| `POST /applications/parse` | Review-first capture | Parses Capture Evidence without writing an Application. |
| `POST /applications/capture` | Optional quick capture | Creates an Application immediately when the captured fields are complete and confidence is high enough. |
| `POST /applications/confirm` | Reviewed capture | Writes the user-reviewed Application to Notion. |

All three Application capture requests from the extension include `X-Capture-Token`. `GET /health` follows the local dashboard health contract and does not require the capture token.

The extension should not call Application Analysis, Resume Creation, operator settings, generic Notion CRUD, or PDF routes.

## Side-Panel Layout

Use one compact vertical side panel that remains open while the user interacts with the source page.

Suggested order:

1. **Header And Readiness**: extension title, backend status, refresh action, and settings action.
2. **Capture Actions**: primary review-first action and optional quick-capture action.
3. **Capture Progress**: current page-reading, parsing, confirming, or writing state.
4. **Review Form**: editable parsed fields and Job Content review.
5. **Capture Result**: created, already captured, needs review, or failed result.

Only the sections relevant to the current state should be expanded. The initial side panel should stay compact instead of showing an empty form.

## Header And Readiness

The header should show:

- title: `Application Capture`
- compact backend status
- refresh button
- settings button

The side panel should call `GET /health` when it opens and when the user manually refreshes readiness.

Readiness states:

| State | Side-panel behavior |
| --- | --- |
| Checking | Show a muted status dot and `Checking backend`. |
| Ready | Show a green status dot and `Ready to capture`. |
| Backend offline | Show a red status dot, the configured backend URL, and a retry action. |
| Capture token missing | Show a blocked status and a link or button that opens extension settings. |
| Notion blocked | Show the backend error and exact schema validation failures when returned. |
| Other workflow blocked | Keep capture enabled when capture and Notion are ready, even if Application Analysis or Resume Creation is blocked. |

The extension should interpret health for capture readiness only. A globally blocked `/health` response must not automatically disable capture when the blocking error belongs only to Application Analysis or Resume Creation.

Do not show analysis model, resume model, queue counts, Master Resume readiness, fit-analysis readiness, or PDF readiness in the extension.

## Primary Review-First Capture

The primary action should be labeled **Fill Form**.

Clicking **Fill Form** should:

1. Verify that the backend URL and capture token are configured.
2. Identify the active tab in the current Chrome window.
3. Collect Capture Evidence from the active source page and readable frames.
4. Normalize the collected evidence into the extension request shape.
5. Call `POST /applications/parse`.
6. Render the returned parsed fields in the review form without writing to Notion.

While the action is running:

- disable capture actions
- show a small spinner and `Reading current page`
- move to `Parsing Application` after evidence collection succeeds
- keep the side panel open
- do not clear a previous successful result until the new action has started successfully

If Chrome cannot read the current page, show a specific source-page error. Do not describe Chrome permission or injection failures as backend failures.

## Capture Evidence

Capture Evidence may include:

- current tab URL
- page title
- selected text
- visible text
- semantic HTML
- per-frame evidence
- relevant page metadata

The extension should prefer selected text when the user has deliberately selected the job posting. Otherwise, it should collect readable evidence from the main page and accessible frames.

Chrome-specific collection details should stay behind an Active Tab Evidence module. React components should receive normalized Capture Evidence and should not call `chrome.tabs`, `chrome.scripting`, or frame APIs directly.

Full captured page content may remain in memory while the current review is active. It must not be written to Chrome storage, browser logs, analytics, or persistent extension state.

## Review Form

After a successful parse, show a review form populated from the parsed result.

Fields:

| Field | Behavior |
| --- | --- |
| Application | Derived preview using `{Role} at {Company Name}`. Not independently editable. |
| Company Name | Editable and required before confirmation. |
| Role | Editable and required before confirmation. |
| Location | Editable when present. Missing Location does not block confirmation unless the backend contract later makes it required. |
| Job URL | Editable and required. Defaults to the canonical URL returned by the backend. |
| Job Content | Show a readable preview for review. Full captured content stays in the current in-memory capture session. |

The form should not expose:

- Application Status
- Analyzed
- Match Score
- Work Type
- Employment Type
- salary or application-management dates
- Notion page IDs or database IDs
- raw HTML
- parser confidence internals
- backend prompts or raw model responses

Capture owns the required creation fields and Capture Defaults. Application management remains in Notion.

### Confirm Action

The primary form action should be labeled **Create in Notion**.

Clicking it should call `POST /applications/confirm` with the reviewed parsed fields and the Job Content retained for the current capture session.

Before sending:

- require Company Name
- require Role
- require Job URL
- require readable Job Content
- update the derived Application title from the final Company Name and Role
- prevent duplicate submissions while confirmation is active

While confirming:

- disable the form action
- keep the reviewed values visible
- show a small spinner and `Creating Application`
- preserve the form if the request fails

## Optional Quick Capture

The side panel may include a secondary **Quick Capture** action that calls `POST /applications/capture` with the current Capture Evidence.

Quick Capture should never bypass backend confidence, duplicate detection, schema validation, or readable Job Content requirements.

Possible results:

| Result | Side-panel behavior |
| --- | --- |
| `created` | Show the created Application summary and Notion link. |
| `already_captured` | Show the existing Application summary and Notion link. Do not treat it as an error. |
| `needs_review` | Populate and open the review form with returned fields and reasons. |
| failed request | Show the error and keep a retry or review-first action available when safe. |

Quick Capture is secondary to **Fill Form**. It should not become the only or visually dominant capture path.

## Capture Result

The result area should show a concise, safe summary.

### Created

Show:

- `Application created`
- Application title
- Company Name
- Role
- Location when present
- **Open in Notion** link
- **Capture another Application** action

### Already Captured

Show:

- `Application already captured`
- existing Application title
- Company Name and Role
- **Open in Notion** link
- calm explanation that the canonical Job URL already exists

This is an idempotent success state, not a failure.

### Needs Review

Show:

- `Review required`
- safe backend reasons
- populated review form
- focus on the first missing or invalid required field

Do not discard captured evidence while the user is correcting the form.

### Failed

Show:

- concise backend or extension error messages
- Notion validation failures with exact database and property names when returned
- retry action when repeating the request is safe
- settings action when configuration is the likely cause

Do not show raw response bodies, full Job Content, stack traces, tokens, or request headers.

## Page And Tab Changes

The side panel may remain open while the active tab or source-page URL changes.

The extension should treat Capture Evidence as belonging to the tab and URL from which it was collected. Before confirmation, if the active tab has changed, keep the existing review form but clearly identify that it belongs to the previously captured source page.

Do not silently replace an in-progress review when:

- the user switches tabs
- the source page navigates
- the side panel regains focus
- readiness refreshes

A new **Fill Form** or **Quick Capture** action may replace the current review only after the user intentionally starts a new capture. If the current form has edits, ask for confirmation before discarding them.

## Extension Settings

The extension settings surface should manage only:

| Setting | Behavior |
| --- | --- |
| Backend URL | Local FastAPI base URL used by the capture client. |
| Capture token | Secret used only for `X-Capture-Token` on protected extension routes. |
| Display preferences | Optional non-secret side-panel preferences. |

The settings surface should provide:

- save action
- masked capture-token input
- connection test using `GET /health`
- success or failure result
- reset to the documented local backend URL

The extension must not store or request:

- Notion token
- Notion database IDs
- DeepSeek key
- model selection
- prompts
- Master Resume content
- export path

Use `chrome.storage.local` for extension settings. Never render the stored capture token back as plain text after saving it.

## Side-Panel State Rules

| State | Extension behavior |
| --- | --- |
| Initial loading | Show compact readiness loading state. |
| Ready and idle | Enable **Fill Form** and the optional **Quick Capture** action. |
| Restricted Chrome page | Explain that Chrome does not allow the page to be read and disable capture for that tab. |
| Reading page | Disable capture actions and show collection progress. |
| Parsing | Keep actions disabled and show parsing progress. |
| Reviewing | Show editable fields and enable confirmation when required values are present. |
| Confirming | Disable duplicate submission and preserve reviewed values. |
| Created | Replace the form with a success result and output link. |
| Already captured | Show the existing Application as a successful idempotent result. |
| Needs review | Keep the review form open with backend reasons. |
| Backend offline | Preserve any in-progress form, show retry, and allow settings access. |
| Notion blocked | Preserve captured values and show exact schema failures. |

## Shared React Components

The extension may share small UI primitives with the React web app, but extension-specific workflow components remain owned by the extension.

| Component | Used for |
| --- | --- |
| `Button` | Fill Form, Quick Capture, Create in Notion, retry, and reset actions. |
| `IconButton` | Refresh, settings, close, and external-link actions. |
| `StatusDot` | Backend and capture readiness. |
| `StatusBadge` | `ready`, `reading`, `parsing`, `review`, `creating`, `created`, `already_captured`, or `failed`. |
| `Spinner` | Inline evidence collection, parsing, and confirmation states. |
| `ErrorCallout` | Backend, Chrome permission, schema, validation, and workflow errors. |
| `SchemaErrorList` | Exact Notion database and property validation failures. |
| `TextInput` | Company Name, Role, Location, and Job URL. |
| `ContentPreview` | Safe readable Job Content preview without raw HTML. |
| `ReviewForm` | Parsed Application review and confirmation. |
| `CaptureProgress` | Current collection and backend action state. |
| `CaptureResultView` | Created, already captured, needs-review, and failed results. |
| `ApplicationSummary` | Safe Application title, Company Name, Role, and Location summary. |

Shared components must work within the narrow side-panel width. The extension should not import dashboard page components or dashboard workflow state.

## Extension Modules

Keep Chrome and transport details behind small interfaces.

| Module | Interface | Hides |
| --- | --- | --- |
| Active Tab Evidence | `collectCaptureEvidence()` | Active-tab lookup, scripting permissions, frame reads, selected text, visible text, semantic HTML, and metadata. |
| Capture Evidence | `createCaptureEvidence(raw)` | Frame normalization, empty-content filtering, and backend request shape. |
| Extension Settings | `getExtensionSettings()`, `saveExtensionSettings()` | Chrome storage, local defaults, and masked token handling. |
| Capture Client | `health()`, `parse(evidence)`, `capture(evidence)`, `confirm(parsed)` | Backend URL, `X-Capture-Token`, JSON handling, and response normalization. |
| Side-Panel Session | `startCapture()`, `updateReview()`, `clearCapture()` | In-memory evidence, parsed fields, dirty-form state, and result transitions. |

React components should render these module results. They should not implement URL canonicalization, duplicate detection, parser confidence rules, Notion schema validation, or workspace writes.

## Chrome Manifest And Permission Boundary

The extension should use Chrome Manifest V3 with:

- a side-panel entry point
- a background service worker
- `activeTab`
- `scripting`
- `sidePanel`
- `storage`
- local backend host permissions

Clicking the extension action should open the side panel for the active tab. The user-action permission path must remain synchronous enough for `chrome.sidePanel.open()` to retain Chrome's required user gesture.

Host permissions should be limited to documented local backend origins. The extension should not request broad remote host access for Notion or DeepSeek because those calls belong to FastAPI.

## Privacy And Logging Rules

- Keep full Capture Evidence only for the active side-panel session.
- Clear in-memory Capture Evidence when the review is completed, discarded, or the side panel session ends.
- Do not persist Job Content in Chrome storage.
- Do not send private content to analytics or third-party logging services.
- Do not log capture tokens, request headers, full visible text, semantic HTML, or full backend responses.
- Development logs may include safe counts, route names, state transitions, and redacted URLs.
- Open Notion links in a new tab with safe external-link behavior.

## Accessibility And Responsive Behavior

The side panel should remain usable at narrow Chrome side-panel widths.

- Use a single-column form.
- Keep primary actions visible without horizontal scrolling.
- Associate every input with a visible label.
- Move focus to the first invalid field after validation fails.
- Announce readiness, pending, success, and failure changes through an accessible live region.
- Do not rely on color alone for status.
- Keep keyboard focus inside confirmation dialogs when warning about discarded edits.
- Allow long URLs and error messages to wrap without widening the panel.

## Testing Surface

The React extension should have focused tests for:

- initial readiness states
- missing capture-token behavior
- active-tab and restricted-page failures
- Capture Evidence normalization
- review-first parse and form population
- required-field validation
- confirmation request construction
- created and already-captured results
- `needs_review` transitions
- preservation of edited form state after backend failure
- dirty-form protection when starting a new capture
- settings persistence without exposing the saved token
- Chrome action opening the side panel
- API client inclusion of `X-Capture-Token`
- absence of full Job Content in persistent storage and logs

Backend contract fixtures should come from the FastAPI OpenAPI-generated client so the extension does not maintain a second handwritten interpretation of route responses.
