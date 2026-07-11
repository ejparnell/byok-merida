# Prototype the critical dashboard and extension interactions

Type: prototype
Labels: ready-for-agent
Status: resolved
Blocked by: none
Map: [Make the Merida final app implementation-ready](../map.md)

## Question

Do rough, disposable prototypes of the single-page `/dashboard` and React side panel make the reviewed readiness, eligible-queue, pending/final-result, review-first capture, dirty-form, and output-link behaviors understandable and usable, and what interaction contract should the final specification preserve?

## Problem Statement

Merida has a reviewed target workflow, but its most important operator interactions span two different local surfaces: the `/dashboard` LLM process console and the Chrome side panel used for Capture. Without exercising those interactions as a whole, the final implementation could technically satisfy individual routes while still leaving operators unclear about what can run, whether a request is still active, what changed after a successful run, whether a reviewed Capture belongs to the current Source Page, or where a completed Resume can be opened.

The working Node prototype does not settle this question. It uses separate server-rendered Analysis and Resume pages, exposes an older extension popup, streams Analysis results, and contains a known missing-result-element defect. The final app must preserve the trustworthy workflow outcomes while intentionally replacing those incidental surfaces.

## Solution

Keep two explicitly disposable React prototypes: one for the single `/dashboard` and one for the focused Chrome side panel. Both use deterministic in-memory data and simulated boundary responses; neither calls the backend, Chrome APIs, Notion, DeepSeek, or PDF storage.

Use the prototypes to validate an operator-facing interaction contract, not implementation architecture. The dashboard is a compact local workflow console with readiness, eligible-only queues, action-pending feedback, short-lived final results, and durable Resume output links. The side panel is a review-first Capture flow that preserves the current review through failed connectivity and Source Page changes, then writes only after the operator explicitly confirms it.

The selected visual direction is the Workflow Overview dashboard and Focused Flow side panel in both Citron & Ink light and Midnight Lime dark themes. These are visual decisions from a throwaway study; the production implementation must preserve the interaction rules below, not the prototype components, mock data, layout markup, or timers.

## User Stories

1. As a Merida operator, I want one `/dashboard` to show the local workflow state, so that I do not have to switch among separate Analysis and Resume pages.
2. As a Merida operator, I want the dashboard to show readiness before I start an LLM action, so that I know whether the local backend and required dependencies can safely run.
3. As a Merida operator, I want Settings, Notion, Application Analysis, Resume Creation, and overall readiness shown distinctly, so that I can identify the affected capability when the workspace is blocked.
4. As a Merida operator, I want non-secret model and provider summaries on the dashboard, so that I can understand the active local configuration without exposing credentials.
5. As a Merida operator, I want Application Analysis and Resume Creation to remain independently usable when their own readiness permits it, so that an unrelated blocked check does not unnecessarily stop work.
6. As a Merida operator, I want the dashboard to show only eligible Applications, so that each visible action can run now and I do not have to interpret row-level exclusion reasons.
7. As a Merida operator, I want Notion to remain the place to edit Applications, Resumes, and Notes, so that the dashboard stays a focused LLM process console rather than a second record-management system.
8. As a Merida operator, I want the Application Analysis preview to show a compact, cursor-paginated queue, so that I can see upcoming work without loading or exposing full Job Content.
9. As a Merida operator, I want the analysis batch control constrained to one through ten Applications, so that the local workflow remains bounded and predictable.
10. As a Merida operator, I want the visible Analysis queue to be clearly a preview rather than a manual selection, so that I understand the backend processes the next eligible batch instead of the current page.
11. As a Merida operator, I want a clear `Running analysis` state with the action disabled and the queue muted, so that I cannot accidentally start the same batch twice.
12. As a Merida operator, I want one final Analysis summary with safe per-Application outcomes, so that I can tell what completed, failed, or repaired without following streaming events.
13. As a Merida operator, I want an Analysis success to refresh readiness and return both queues to their first pages, so that newly analyzed Applications visibly move into Resume Creation.
14. As a Merida operator, I want an Analysis failure to retain the current queue page unless work completed or repaired, so that I do not lose my place after an unsuccessful request.
15. As a Merida operator, I want Resume Creation to show only analyzed Applications eligible for a first Job-Specific Resume, so that I do not retry records that already have a Resume Attachment.
16. As a Merida operator, I want a read-only Match Score beside each eligible Resume Creation item, so that I can prioritize without editing scoring data in the dashboard.
17. As a Merida operator, I want Resume Creation to be one Application at a time, so that artifact creation and its cleanup behavior remain understandable and safe.
18. As a Merida operator, I want a row-level `Creating resume` state and duplicate-click protection, so that I know which Application is active without losing the rest of the queue.
19. As a Merida operator, I want a created or `already_created` Resume result to retain Resume, Resume Fit Analysis Note, and PDF links after the queue row disappears, so that I can immediately inspect the durable outputs.
20. As a Merida operator, I want a failed Resume result to explain returned errors and cleanup status, so that I know whether a retry is safe or manual workspace attention is needed.
21. As a Merida operator, I want transient dashboard success and failure notices to be dismissible and short-lived, so that feedback is visible without turning the console into a history log.
22. As a Chrome extension user, I want the side panel to show Capture-specific readiness, so that an Application Analysis or Resume Creation problem does not incorrectly prevent Capture.
23. As a Chrome extension user, I want **Fill Form** to be the primary Capture action, so that Merida reads the Source Page and lets me review it before any Notion write.
24. As a Chrome extension user, I want visible `Reading current page` and `Parsing Application` progress, so that Chrome page-access failures are distinguishable from backend failures.
25. As a Chrome extension user, I want the parsed Company Name, Role, Location, Job URL, and readable Job Content displayed in an editable review form, so that I can correct important Capture fields before creation.
26. As a Chrome extension user, I want the Application title derived from my final Company Name and Role, so that the title cannot drift from the fields that define it.
27. As a Chrome extension user, I want required-field validation before **Create in Notion**, so that incomplete Capture data is not sent as a writable Application.
28. As a Chrome extension user, I want my edited review values to remain visible while confirmation is pending or after a request fails, so that I do not lose work because of a transient failure.
29. As a Chrome extension user, I want Capture Evidence to remain in memory only for the active review, so that private Job Content is not retained in extension storage or logs.
30. As a Chrome extension user, I want a change of active tab or Source Page to warn me that the review belongs to the earlier page, so that Merida never silently swaps in unrelated source evidence.
31. As a Chrome extension user, I want a new Capture action to ask before discarding a dirty review, so that deliberate edits are not lost.
32. As a Chrome extension user, I want `created` and `already_captured` to be calm successful Capture results with an Open in Notion link, so that canonical duplicate protection does not feel like an error.
33. As a Chrome extension user, I want `needs_review` to keep the form open with safe reasons and focus the first required correction, so that I can finish the Capture without re-reading the page.
34. As a Chrome extension user, I want an offline or Notion-blocked state to preserve the review and offer a retry or settings action, so that a local configuration problem does not destroy captured work.
35. As a future implementation agent, I want visual-theme choices distinguished from behavioral requirements, so that the prototype can be deleted without losing the accepted operator contract.
36. As a future implementation agent, I want dashboard and side-panel behavior verified through their public interaction seams, so that tests protect what operators see rather than copied prototype internals.

## Implementation Decisions

- The final web surface is one React `/dashboard` LLM process console. It contains Health and Settings, Application Analysis, and Resume Creation sections in that order. It is not an Application, Resume, or Note editor; Notion remains the management surface.
- The final Capture surface is a React Chrome Manifest V3 side panel. It is responsible only for Capture readiness, Active Tab Evidence collection, review-first parsing, reviewed confirmation, and Capture results. It does not run Application Analysis, Resume Creation, PDF generation, generic Notion CRUD, or backend configuration.
- The chosen visual direction from the disposable prototype is Workflow Overview for the dashboard and Focused Flow for the side panel. Citron & Ink is the light appearance and Midnight Lime is the dark appearance. Production may refine responsive layout and component composition without reopening the accepted interaction hierarchy.
- The dashboard loads health, non-secret operator settings, the first Application Analysis Queue page, and the first Resume Creation Queue page. Queue count is owned by each queue response, not by health. Cursor values are opaque and are passed back unchanged.
- Dashboard queues are eligible-only. The dashboard never renders blocked or ineligible records with explanation rows; the operator corrects those records in Notion. The empty state may direct the operator to Notion or Capture as the next useful action.
- Application Analysis has one action state for the whole bounded batch. It accepts a limit from `1` through `10`, disables repeat submission while pending, leaves the preview list visible but muted, and renders one final safe result. The backend selects the next eligible batch independently of the visible cursor page.
- After an Analysis success, dashboard health is refreshed and both queues return to page one. After a route-level Analysis failure, health is refreshed and pagination remains unchanged unless the response reports completed or repaired items.
- Resume Creation is a per-Application action. The active row shows pending feedback and blocks duplicate submission for that Application; any broader concurrent-action restriction must come from the later concurrency and recovery decision, not from the prototype. A success removes the Application from the queue after refresh while keeping the output result visible. `already_created` is a success with existing output links, not an error.
- Dashboard result messages are intentionally temporary, manually dismissible feedback rather than a run-history feature. The prototype used an eight-second automatic dismissal; production may implement the same accessible behavior, but the requirement is clear, non-sticky feedback with no loss of output links that the operator still needs.
- The side panel starts compact with Capture readiness and **Fill Form**. The primary flow collects normalized Capture Evidence, parses without a workspace write, presents reviewable values, and calls reviewed confirmation only after the operator selects **Create in Notion**. Quick Capture is not part of v1.
- The side panel owns an in-memory Capture Session containing the normalized Capture Evidence, parsed values, source-tab identity, dirty-form state, pending operation, and final result. Full Job Content is cleared when the review is completed, discarded, or the side-panel session ends and is never written to extension persistence.
- A review belongs to the tab and canonical Source Page from which its evidence was collected. Tab changes, page navigations, side-panel focus, and readiness refreshes cannot silently replace an open review. Starting a new Capture while review fields are dirty requires an explicit discard confirmation.
- The derived Application title is computed from the reviewed Role and Company Name. The form exposes only Company Name, Role, optional Location, Job URL, and a safe readable Job Content review; it does not expose parser internals, Notion identifiers, raw HTML, Application management fields, prompts, or raw model responses.
- The Capture Session preserves edited form values for confirmation failures, backend-offline states, and Notion schema blocks. Created and `already_captured` are terminal successful results that offer a Notion link. `needs_review` remains an editable state rather than a terminal failure.
- The disposable prototypes record the following interaction state shapes. They are behavioral reference material, not production code:

  ```text
  Dashboard Analysis: idle -> running -> completed | route_failed
  Dashboard Resume: ready(item) -> creating(item) -> created | already_created | blocked | failed
  Capture: idle -> reading -> parsing -> reviewing -> confirming
                                 |                 -> created | already_captured | needs_review | failed
  Reviewing + source change: reviewing(previous source, dirty or clean) -> warned reviewing(previous source)
  ```

- The public interaction seams are intentionally separate because the dashboard and extension have different authority boundaries. The dashboard session receives typed dashboard-client responses and exposes rendered readiness, queues, actions, and result state. The side-panel Capture Session receives Active Tab Evidence, extension settings, and typed Capture-client responses and exposes rendered Capture state. Chrome APIs, route transport, Notion writes, and LLM behavior remain behind those seams.
- This issue does not lock final module ownership, transport schemas, workspace adapter mapping, concurrency policy, demo adapter policy, or runtime topology. Those remain owned by their named Wayfinder tickets.

## Testing Decisions

- A good interaction test drives an operator-visible action through a public dashboard or Capture Session seam and asserts visible state, enabled or disabled actions, safe result text, retained form values, output-link availability, and the boundary request it causes. It does not assert hook names, component tree shape, mock timer counts, CSS class names, or private helper calls.
- Dashboard interaction tests cover initial loading, independently blocked and ready sections, eligible-only empty and populated queues, opaque cursor paging, `1..10` batch clamping, Analysis pending state, a final multi-item Analysis result, success refresh/page reset, failure pagination retention, row-level Resume Creation pending state, duplicate-click protection, `created`, `already_created`, blocked, and failed Resume outcomes, cleanup display, and retained Resume/Note/PDF links after queue refresh.
- Capture interaction tests cover missing Capture token, Capture-specific readiness, restricted-page failures, active-tab evidence collection, parse-to-review flow, required-field validation, derived-title updates, confirmation request construction, created, already-captured, needs-review, offline, and Notion-schema outcomes, preserved edits after failure, source-page change warning, dirty-review discard confirmation, masked settings, and the absence of full Job Content from persistent extension storage and logs.
- Use deterministic fake dashboard and Capture clients. The fakes return reviewed typed route outcomes and record requested actions; they do not emulate Notion, DeepSeek, Chrome APIs, PDF files, or timing-sensitive streaming transport.
- UI-level assertions are the highest useful seam for this ticket. The pre-existing versioned parity harness remains responsible for backend workflow effects, evidence validation, idempotency, persistence order, artifacts, and cleanup. Route tests remain responsible for HTTP authentication, validation, and status mapping.
- Existing dashboard and side-panel prototypes are prior art for pending, final-result, source-change, offline, and narrow-screen presentation. The existing Capture service, Application Analysis service, Resume Creation service, and parity fixtures remain prior art for the typed outcomes displayed by the UI.
- Browser verification for the disposable prototypes consists of their documented development commands plus a production build. The prototype itself needs no durable test suite; final production surfaces need focused interaction tests at the two public seams above.
- Accessibility tests must verify visible labels, keyboard-operable actions, focus on the first invalid Capture field, accessible pending/success/failure announcements, wrapped long URLs and errors at side-panel width, and status meaning that is not color-only.

## Out of Scope

- Implementing the FastAPI backend, React production dashboard, React Chrome extension, generated API client, LangGraph workflows, Notion adapter, or migration.
- Turning the dashboard into a Notion record-management interface or adding Application, Resume, or Note editing outside Notion.
- Quick Capture, batch Resume Creation, missing-PDF repair, Application selection from a dashboard preview, general Notes behavior, model selection, or a run-history console.
- Designing exact HTTP schemas, route prefixes, auth headers, workspace mappings, generated TypeScript names, error taxonomy, concurrency locks, crash recovery, demo persistence, runtime packaging, or repository topology.
- Persisting Capture Evidence, private Job Content, prompts, raw model output, credentials, or local artifact paths in browser storage, normal dashboard state, analytics, or normal logs.
- Treating the prototype's mock data, artificial delays, current component names, exact timer duration, responsive markup, or visual CSS implementation as production architecture.
- Reproducing the legacy extension's missing result element, the old popup surface, separate Node-rendered `/analysis` and `/resumes` pages, or streamed Analysis UI events.

## Further Notes

- The final app preserves observable product outcomes and safety rules, not legacy page routes, NDJSON transport, or the current extension's DOM structure.
- The side panel's review-first **Fill Form** path is authoritative. The optional Quick Capture path remains excluded from v1.
- Exact public response DTOs and the future generated client belong to the API-client contract ticket. This specification relies on the reviewed semantic outcomes without settling their final JSON representation.
- Full private Capture Evidence may be held only for the active in-memory review. Dashboard results and side-panel results use safe, compact summaries.
- Prototype code is explicitly disposable. This issue, the reviewed route and frontend contracts, and focused future interaction tests are the durable record after the prototypes are deleted or absorbed.

## Answer

The disposable dashboard and side-panel prototypes were reviewed and build successfully. They establish the Workflow Overview dashboard and Focused Flow side panel in Citron & Ink light and Midnight Lime dark appearances, with review-first **Fill Form** as the only v1 Capture action.

The implementation-ready interaction contract is recorded above: two public interaction seams cover the dashboard operator session and Capture side-panel session; queues are eligible-only; dashboard work uses pending state plus one final result; Resume outputs stay linked after queue refresh; Capture protects dirty reviewed values and prior Source Page provenance; and private Job Content stays in the in-memory Capture Session only.

Resolution assets:

- [Dashboard prototype](../../../apps/web-prototype/)
- [Extension side-panel prototype](../../../apps/extension-prototype/)
- [Dashboard prototype notes](../../../apps/web-prototype/NOTES.md)
- [Extension prototype notes](../../../apps/extension-prototype/NOTES.md)
- [Prototype parity inventory](../assets/prototype-parity-inventory.md)
