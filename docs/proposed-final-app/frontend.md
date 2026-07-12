# Frontend - Proposed

The proposed web app is a single React page at `/dashboard`. The page is an LLM process console for the local workflow, not a marketing page, not a general Notion database editor, and not the place to manage job application records.

The dashboard has three sections:

1. Health and operator settings.
2. Application Analysis.
3. Resume Creation.

The Chrome extension remains responsible for capturing Applications. Notion remains responsible for editing and real management of Applications, Resumes, and Notes. The dashboard starts after Applications already exist in the workspace and only shows LLM actions that can run now.

## Page Goals

- Show whether the backend is ready before the user starts LLM work.
- Show non-secret, read-only settings that affect LLM runs, especially selected models and configured providers.
- Let the user run Application Analysis for eligible captured Applications.
- Let the user create one Job-Specific Resume at a time from eligible analyzed Applications.
- Keep pending, success, and failure states visible while backend work is happening.
- Avoid exposing secrets, prompts, full private Job Content, or full raw model responses.

## Data Loaded On Page Open

| Route | Used by | Purpose |
| --- | --- | --- |
| `GET /health` | Health section and section readiness | Shows overall backend readiness and blocking errors. |
| `GET /operator/settings` | Health section | Shows selected models and configured provider flags without a runtime-mode discriminator. |
| `GET /applications/analysis/queue?limit=5` | Application Analysis section | Lists eligible Applications ready to analyze. |
| `GET /resumes/queue?limit=5` | Resume Creation section | Lists eligible analyzed Applications that can create a resume. |

The dashboard should call only `GET /health` for health state in v1. Narrower health routes are diagnostic routes, not part of the default page load.

Queue counts come from queue routes, not from health routes.

The page should refresh dashboard data after analysis and resume creation because both workflows change queue membership.

## Page Layout

Use one vertical dashboard page with stacked sections. Each section should have a compact header, current status, primary action, and a list or result area.

Suggested order:

1. **Health And Settings**: readiness bar, model cards, provider configuration dots.
2. **Application Analysis**: eligible analysis queue, batch controls, pending state, result summary.
3. **Resume Creation**: eligible resume queue, per-Application create buttons, pending state, output links.

The page should work comfortably on a laptop screen without requiring the user to understand the backend routes.

## Health And Settings Section

This section tells the user whether the app is fully ready to operate. Partial readiness is allowed: the global status can be blocked while one section remains runnable.

### Readiness Bar

Show a horizontal readiness bar with these segments:

| Segment | Source | Ready when |
| --- | --- | --- |
| Settings | `/health.checks.settings` | Settings check is `ready`. |
| Notion | `/health.checks.notion` | Notion check is `ready`. |
| Analysis | `/health.checks.analysis` | Analysis check is `ready`. |
| Resumes | `/health.checks.resumes` | Resumes check is `ready`. |
| Ready | `/health.status` | Status is `ready`. |

Each segment should use a status color and label:

- `ready`: green.
- `blocked`: red.
- `not_checked`: neutral gray.
- loading or unknown: muted gray with spinner.

If `/health.errors` contains messages, show them in a compact global callout below the bar. Also show section-level callouts filtered to the affected workflow:

| Error type | Where to show |
| --- | --- |
| Applications schema or Job Content access issue | Global and Application Analysis. |
| Missing DeepSeek configuration | Global, Application Analysis, and Resume Creation. |
| Master Resume evidence or analysis-matcher readiness issue | Global, Application Analysis, and Resume Creation. |
| Resumes, Notes, resume fit-analysis, or PDF readiness issue | Global and Resume Creation. |

If an error is a Notion validation failure, show exact database and property names from the backend response so the user can correct the schema in Notion.

### Operator Settings

Show a compact settings summary from `GET /operator/settings`.

Display two small read-only model cards:

| Card | Value |
| --- | --- |
| Analysis model | `models.analysis` |
| Resume model | `models.resumes` |

Under the model cards, show provider configuration dots:

| Dot | Source | Green when |
| --- | --- | --- |
| Notion | `configured.notion` | `true` |
| DeepSeek | `configured.deepseek` | `true` |

Do not show capture token status, export paths, actual tokens, Notion IDs, Notion token, DeepSeek key, prompts, or raw private content.

The dashboard does not allow changing models in v1. Model selection stays in backend configuration.

## Application Analysis Section

This section lets the user run Application Analysis for eligible captured Applications.

The queue is eligible-only. The dashboard should not show blocked or ineligible Applications with row-level reasons. The user manages status and record fixes in Notion.

### Header

The header should show:

- Section title: `Application Analysis`.
- Queue count from `GET /applications/analysis/queue?limit=5`.
- Analysis model from `GET /operator/settings`.
- A ready or blocked status indicator derived from `/health.checks.analysis`.

### Controls

Place these controls on one line when there is enough horizontal space:

| Control | Behavior |
| --- | --- |
| Batch limit input | Numeric input for how many Applications to process. Defaults to `5`, clamps to `1` through `10`. |
| Run Analysis button | Calls `POST /applications/analysis/run`. Disabled when analysis is blocked, queue is empty, or a run is already active. |
| Queue count | Shows how many Applications are waiting for analysis. |
| Refresh button | Reloads `/health`, `/operator/settings`, `/applications/analysis/queue`, and `/resumes/queue`. |

### Queue List

Render a compact list of Applications from `GET /applications/analysis/queue?limit=5`.

Each row should show:

- company name
- role

The list should not show full Job Content. Application IDs may be available in dev tooling, but they should not be a primary UI element.

The list should use backend pagination. The frontend should keep the current opaque cursor and send the returned `nextCursor` for the next page. The frontend must not parse or modify cursor values.

### Run State

When the user clicks **Run Analysis**, keep the UI simple:

- disable the run button
- show a small spinner and `Running analysis`
- keep the current queue visible but visually muted
- wait for the backend response
- show the final summary returned by the backend
- show safe per-Application results from the response when present

The run action processes the backend's next eligible batch by `limit`, independent of the currently visible pagination cursor. The visible list is a preview, not a selection mechanism.

After a successful response, refresh `/health`, reset the Application Analysis queue to page one, and reset the Resume Creation queue to page one so newly analyzed Applications move between sections.

After a failed response, refresh `/health` and keep queue pagination unchanged unless the backend reports completed or repaired items.

## Resume Creation Section

This section lets the user create Job-Specific Resumes from eligible analyzed Applications.

Resume Creation is row-level and one-at-a-time for v1. There is no batch resume button.

The queue is eligible-only. Applications with existing Resumes do not appear in the queue, even if a PDF is missing.

### Header

The header should show:

- Section title: `Resume Creation`.
- Queue count from `GET /resumes/queue?limit=5`.
- Resume model from `GET /operator/settings`.
- A ready or blocked status indicator derived from `/health.checks.resumes`.

### Queue List

Render analyzed Applications from `GET /resumes/queue?limit=5`.

Each row should show:

- company name
- role
- read-only Match Score
- **Create Resume** button

Show five Applications per page. Pagination should use backend `limit` and opaque `cursor` query params, not client-side slicing of a full queue. The frontend must not parse or modify cursor values.

### Create Resume Action

Clicking **Create Resume** should call:

```json
{
  "applicationId": "app_123"
}
```

against `POST /resumes/create`.

While a resume is being created:

- disable the clicked row button
- show row-level pending state
- show a small spinner and `Creating resume`
- prevent duplicate clicks for the same Application

On success, show:

- generated resume link
- related Resume Fit Analysis Note link
- PDF download link
- concise success message

If the backend returns `already_created`, show the existing Resume link and any returned PDF download link without treating it as an error.

On failure, show:

- backend error messages
- cleanup status, if present
- a retry button only when retrying is safe

After success, refresh `/health` and reset the Resume Creation queue to page one so the completed Application leaves the queue. Keep the success result visible after the row leaves the queue.

## Refresh Behavior

The dashboard should feel current without requiring a page reload.

| Trigger | Refresh behavior |
| --- | --- |
| Page load | Load `/health`, `/operator/settings`, first page of `/applications/analysis/queue`, and first page of `/resumes/queue`. |
| Manual refresh | Reload all dashboard data and keep the current queue pages when possible. |
| Analysis success | Reload `/health`, reset `/applications/analysis/queue` to page one, and reset `/resumes/queue` to page one. |
| Analysis failure | Reload `/health` and leave queue pagination unchanged unless the backend reports completed or repaired items. |
| Resume creation success | Reload `/health`, reset `/resumes/queue` to page one, and keep result links visible after the row leaves the queue. |
| Resume creation failure | Reload `/health`, keep the row visible, and show backend errors plus cleanup status. |

## Page State Rules

| State | Dashboard behavior |
| --- | --- |
| Initial loading | Show section skeletons or compact loading rows. |
| Backend offline | Show a top-level blocking callout and disable run/create actions. |
| Notion blocked | Keep the page visible, show exact schema/config validation messages, and disable affected write actions. |
| DeepSeek missing | Disable Application Analysis and Resume Creation, but keep queue lists readable when possible. |
| Analysis ready while Resumes blocked | Enable Application Analysis and disable Resume Creation. |
| Resumes ready while Analysis blocked | Keep Resume Creation usable if the queue route returns eligible Applications. |
| Analysis running | Disable the run button and show a pending state until the final response returns. |
| Resume creation running | Disable only the active row button unless the backend cannot safely run multiple creations. |
| Empty queue | Show a calm empty state with the next useful action in Notion or the Chrome extension. |

## Shared Components

These components should be shared across dashboard sections.

| Component | Used for |
| --- | --- |
| `Button` | Primary actions, secondary refresh actions, retry actions. |
| `IconButton` | Compact refresh, open link, and download actions. |
| `Card` | Model summaries, queue rows on narrow screens, and result summaries. |
| `SectionPanel` | Top-level dashboard sections with a header and content body. |
| `SectionHeader` | Title, subtitle, status indicator, and small section actions. |
| `StatusDot` | Boolean or readiness indicators. |
| `StatusBar` | Health readiness bar with multiple segments. |
| `StatusBadge` | Text status such as `ready`, `blocked`, `running`, `created`, `already_created`, or `failed`. |
| `ModelCard` | Small read-only display card for selected analysis and resume models. |
| `ConfiguredDots` | Notion and DeepSeek configuration indicators. |
| `NumberInput` | Batch limit input for Application Analysis. |
| `QueueTable` | Desktop list of Applications. |
| `QueueRow` | Shared row shape for analysis and resume queues. |
| `Pagination` | Backend cursor paging for Application Analysis and Resume Creation queues. |
| `ActionStatus` | Pending, success, and failure states for run/create actions. |
| `ResultSummary` | Final response summary after analysis or resume creation. |
| `ResultItemList` | Safe per-Application result rows from analysis. |
| `Spinner` | Inline running state. |
| `EmptyState` | Empty queues or no results. |
| `ErrorCallout` | Blocking health, route, schema, or workflow errors. |
| `SchemaErrorList` | Exact Notion validation failures with property names and database names. |
| `ResultLinks` | Resume, Note, and PDF output links after resume creation. |
