# Frontend

The web app is a single React page at `/dashboard`. The page is an LLM process console for the local workflow, not a marketing page, not a general Notion database editor, and not the place to manage job application records.

The dashboard has three sections:

1. Health and operator settings.
2. Application Analysis.
3. Resume Creation.

The Chrome extension remains responsible for capturing Applications. Notion remains responsible for editing and real management of Applications, Resumes, and Notes. The dashboard starts after Applications already exist in the workspace and only shows LLM actions that can run now.

## Page Goals

- Show whether the backend is ready before the user starts LLM work.
- Show non-secret, read-only settings that affect LLM runs, especially selected models and configured providers.
- Let the user start, follow, reconnect to, and cancel a durable Application Analysis Run.
- Let the user create one Job-Specific Resume at a time from eligible analyzed Applications.
- Keep pending, success, and failure states visible while backend work is happening.
- Avoid exposing secrets, prompts, full private Job Content, or full raw model responses.

## Data Loaded On Page Open

| Route                                      | Used by                              | Purpose                                                                                   |
| ------------------------------------------ | ------------------------------------ | ----------------------------------------------------------------------------------------- |
| `GET /health`                              | Health section and section readiness | Shows overall backend readiness and blocking errors.                                      |
| `GET /operator/settings`                   | Health section                       | Shows selected models and configured provider flags without a runtime-mode discriminator. |
| `GET /applications/analysis/queue?limit=5` | Application Analysis section         | Lists eligible Applications ready to analyze.                                             |
| `GET /applications/analysis/runs/active`   | Application Analysis section         | Reconnects to an unfinished durable Analysis Run after load or reload.                    |
| `GET /resumes/queue?limit=5`               | Resume Creation section              | Lists eligible analyzed Applications that can create a resume.                            |

The dashboard should call only `GET /health` for health state in v1. Narrower health routes are diagnostic routes, not part of the default page load.

Queue counts come from queue routes, not from health routes.

The page should refresh dashboard data after analysis and resume creation because both workflows change queue membership.

## Page Layout

Use one vertical dashboard page with stacked sections. Each section should have a compact header, current status, primary action, and a list or result area.

Suggested order:

1. **Health And Settings**: readiness bar, model cards, provider configuration dots.
2. **Application Analysis**: eligible analysis queue, target control, durable run progress, cancellation, and retained terminal result.
3. **Resume Creation**: eligible resume queue, per-Application create buttons, pending state, output links.

The page should work comfortably on a laptop screen without requiring the user to understand the backend routes.

## Health And Settings Section

This section tells the user whether the app is fully ready to operate. Partial readiness is allowed: the global status can be blocked while one section remains runnable.

### Readiness Bar

Show a horizontal readiness bar with these segments:

| Segment  | Source                    | Ready when                 |
| -------- | ------------------------- | -------------------------- |
| Settings | `/health.checks.settings` | Settings check is `ready`. |
| Notion   | `/health.checks.notion`   | Notion check is `ready`.   |
| Analysis | `/health.checks.analysis` | Analysis check is `ready`. |
| Resumes  | `/health.checks.resumes`  | Resumes check is `ready`.  |
| Ready    | `/health.status`          | Status is `ready`.         |

Each segment should use a status color and label:

- `ready`: green.
- `blocked`: red.
- `not_checked`: neutral gray.
- loading or unknown: muted gray with spinner.

If `/health.errors` contains messages, show them in a compact global callout below the bar. Also show section-level callouts filtered to the affected workflow:

| Error type                                                  | Where to show                                      |
| ----------------------------------------------------------- | -------------------------------------------------- |
| Applications schema or Job Content access issue             | Global and Application Analysis.                   |
| Missing DeepSeek configuration                              | Global, Application Analysis, and Resume Creation. |
| Master Resume evidence or analysis-matcher readiness issue  | Global, Application Analysis, and Resume Creation. |
| Resumes, Notes, resume fit-analysis, or PDF readiness issue | Global and Resume Creation.                        |

If an error is a Notion validation failure, show exact database and property names from the backend response so the user can correct the schema in Notion.

### Operator Settings

Show a compact settings summary from `GET /operator/settings`.

Display two small read-only model cards:

| Card           | Value             |
| -------------- | ----------------- |
| Analysis model | `models.analysis` |
| Resume model   | `models.resumes`  |

Under the model cards, show provider configuration dots:

| Dot      | Source                | Green when |
| -------- | --------------------- | ---------- |
| Notion   | `configured.notion`   | `true`     |
| DeepSeek | `configured.deepseek` | `true`     |

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

| Control               | Behavior                                                                                                                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Analysis Batch Target | Number of successful Analysis Completions to pursue. Defaults to `5` and clamps to `1` through `10`; skipped and failed candidates do not satisfy it.               |
| Run Analysis button   | Generates one idempotency key and calls `POST /applications/analysis/run` with `target`. Disabled when analysis is blocked, the queue is empty, or a run is active. |
| Queue count           | Shows how many Applications are waiting for analysis.                                                                                                               |
| Refresh button        | Reloads `/health`, `/operator/settings`, `/applications/analysis/queue`, and `/resumes/queue`.                                                                      |

### Queue List

Render a compact list of Applications from `GET /applications/analysis/queue?limit=5`.

Each row should show:

- company name
- role

The list should not show full Job Content. Application IDs may be available in dev tooling, but they should not be a primary UI element.

The list should use backend pagination. The frontend should keep the current opaque cursor and send the returned `nextCursor` for the next page. The frontend must not parse or modify cursor values.

### Run State

One intentional click creates one client idempotency key. The generated-client
call sends `{ "target": number }` and `Idempotency-Key` exactly once; polling and
transport behavior must never replay that POST. A `202` snapshot gives the
session its run identity immediately. A typed `analysis_run_active` conflict
includes `activeRunId`; follow that run with a GET instead of parsing the error
message or issuing another start.

While a run is active:

- disable **Run Analysis** and show `Queued`, `Running`, or `Cancelling`;
- keep the queue preview visible; it is not the Run Candidate Set;
- poll `GET /applications/analysis/runs/{runId}`;
- show completions against target, evaluated candidates against Attempt Budget,
  and Committed Spend against $0.50 as the primary progress line;
- show verified cost, active reservations, indeterminate reservations, and
  remaining authorized budget as expanded detail;
- show safe candidate states: `analyzed`, `repaired`, `skipped`, `failed`, and
  `indeterminate`, plus safe reason codes where present;
- offer **Cancel run** for `queued`, `running`, and `cancelling` state.

Cancellation prevents future provider calls but cannot promise that an in-flight
call is stopped or refunded. The UI continues polling until the durable terminal
snapshot arrives.

On page load, request `/applications/analysis/runs/active`; if it returns a run,
reconnect and poll it. A finished run displays one of `target_met`,
`spend_limited`, `attempt_budget_exhausted`, `queue_exhausted`, `cancelled`,
`authorization_blocked`, or `failed`. Keep that terminal result visible without
automatic dismissal. Refresh health and reset both queue cursors once when a run
becomes terminal, without clearing the run result.

The start target is independent of the visible queue cursor and its query
`limit`. At creation, the backend fixes the Candidate Set in canonical queue
order and may backfill within its finite Attempt Budget.

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

| Trigger                   | Refresh behavior                                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Page load                 | Load dashboard data plus `/applications/analysis/runs/active`; reconnect and poll when an active run exists.        |
| Manual refresh            | Reload all dashboard data and keep the current queue pages when possible.                                           |
| Analysis becomes terminal | Reload `/health`, reset both queues to page one, and retain the durable terminal run result.                        |
| Analysis poll failure     | Keep the last durable snapshot visible, report the safe error, and allow later polling or refresh to reconnect.     |
| Resume creation success   | Reload `/health`, reset `/resumes/queue` to page one, and keep result links visible after the row leaves the queue. |
| Resume creation failure   | Reload `/health`, keep the row visible, and show backend errors plus cleanup status.                                |

## Page State Rules

| State                                | Dashboard behavior                                                                                       |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Initial loading                      | Show section skeletons or compact loading rows.                                                          |
| Backend offline                      | Show a top-level blocking callout and disable run/create actions.                                        |
| Notion blocked                       | Keep the page visible, show exact schema/config validation messages, and disable affected write actions. |
| DeepSeek missing                     | Disable Application Analysis and Resume Creation, but keep queue lists readable when possible.           |
| Analysis ready while Resumes blocked | Enable Application Analysis and disable Resume Creation.                                                 |
| Resumes ready while Analysis blocked | Keep Resume Creation usable if the queue route returns eligible Applications.                            |
| Analysis queued or running           | Disable the run button, poll the durable snapshot, show progress and spend, and allow cancellation.      |
| Analysis cancelling                  | Disable new starts, show that cancellation was requested, and poll until the run finishes.               |
| Analysis finished                    | Keep the terminal outcome, spend detail, and safe per-Application results visible.                       |
| Resume Run queued or running         | Follow the durable run, show progress and Committed Spend, and disable only Resume Run start.             |
| Empty queue                          | Show a calm empty state with the next useful action in Notion or the Chrome extension.                   |

## Shared Components

These components should be shared across dashboard sections.

| Component         | Used for                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------- |
| `Button`          | Primary actions, secondary refresh actions, retry actions.                                  |
| `IconButton`      | Compact refresh, open link, and download actions.                                           |
| `Card`            | Model summaries, queue rows on narrow screens, and result summaries.                        |
| `SectionPanel`    | Top-level dashboard sections with a header and content body.                                |
| `SectionHeader`   | Title, subtitle, status indicator, and small section actions.                               |
| `StatusDot`       | Boolean or readiness indicators.                                                            |
| `StatusBar`       | Health readiness bar with multiple segments.                                                |
| `StatusBadge`     | Readiness, Analysis Run lifecycle/outcomes, candidate results, and Resume Creation results. |
| `ModelCard`       | Small read-only display card for selected analysis and resume models.                       |
| `ConfiguredDots`  | Notion and DeepSeek configuration indicators.                                               |
| `NumberInput`     | Analysis Batch Target input for successful Analysis Completions.                            |
| `QueueTable`      | Desktop list of Applications.                                                               |
| `QueueRow`        | Shared row shape for analysis and resume queues.                                            |
| `Pagination`      | Backend cursor paging for Application Analysis and Resume Creation queues.                  |
| `ActionStatus`    | Pending, success, and failure states for start, cancel, and create actions.                 |
| `ResultSummary`   | Durable Analysis Run progress/terminal snapshot or Resume Creation result.                  |
| `ResultItemList`  | Safe per-Application candidate states from an Analysis Run.                                 |
| `Spinner`         | Inline running state.                                                                       |
| `EmptyState`      | Empty queues or no results.                                                                 |
| `ErrorCallout`    | Blocking health, route, schema, or workflow errors.                                         |
| `SchemaErrorList` | Exact Notion validation failures with property names and database names.                    |
| `ResultLinks`     | Resume, Note, and PDF output links after resume creation.                                   |
