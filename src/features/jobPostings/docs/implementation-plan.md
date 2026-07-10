# Job Posting Capture Implementation Plan

This plan turns the resolved Job Postings glossary and ADRs into a build checklist for the MVP.

## MVP Target

A local Chrome extension button captures the current rendered job posting page, sends structured Capture Evidence to a token-protected local backend, parses a Job Posting, validates the Configured Notion Database schema, prevents Duplicate Captures by canonical Job URL, and creates a readable Notion page with required properties and Job Content blocks.

## Recommended Structure

Keep feature-owned implementation under `src/features/jobPostings/` unless selected tooling requires root-level entrypoints.

```txt
src/features/jobPostings/
  backend/
  extension/
  lib/
  types/
  docs/
```

Root-level files such as package manifests, build config, or extension build output can exist only when the tooling needs them.

## Phase 1: Shared Contracts

- [ ] Define `CaptureEvidence` with `url`, `pageTitle`, optional `selectedText`, `visibleText`, optional `semanticHtml`, and optional discovered metadata.
- [ ] Define `ParsedJobPosting` with `jobPostingTitle`, `jobUrl`, optional `capturedUrl`, optional `companyName`, optional `jobTitle`, optional `location`, `jobContent`, and parsing notes.
- [ ] Define `CaptureResult` variants: `created`, `already_captured`, `needs_review`, and `failed`.
- [ ] Define failure reasons for backend offline, invalid token, invalid Notion config, invalid Notion schema, duplicate lookup failure, missing job content, and Notion write failure.
- [ ] Keep capture confidence internal; expose only result state and human-readable notes.

## Phase 2: Local Backend

- [ ] Add local config loading for `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `CAPTURE_TOKEN`, optional LLM key, and optional `PORT`.
- [ ] Expose a health/config validation endpoint for extension status checks.
- [ ] Expose a capture endpoint that requires the shared capture token.
- [ ] Restrict CORS to the configured extension origin.
- [ ] Reject requests without a valid capture token before parsing or Notion writes.
- [ ] Treat Notion as the only durable store; do not add a local database or retry queue for MVP.

## Phase 3: Notion Integration

- [ ] Validate the existing Notion database schema before capture writes.
- [ ] Require `Job Posting` title, `Company Name` rich text, `Job Title` rich text, `Job URL` URL, `Location` rich text, `Application Status` select, `Match Score` number, `Application Date` date, and `Analyzed` checkbox.
- [ ] Treat `Captured URL` as optional but supported when present.
- [ ] Validate that the `Application Status` select contains `To Apply`; do not create or mutate schema/options.
- [ ] Query by canonical `Job URL` before creating a page.
- [ ] Return `already_captured` with the existing Notion page link when a duplicate exists.
- [ ] Create pages with `Application Status = To Apply`, `Analyzed = unchecked`, blank `Match Score`, and blank `Application Date`.
- [ ] Use `Job Posting` as the title value, normally `{Job Title} at {Company Name}`.

## Phase 4: Parsing Pipeline

- [ ] Canonicalize Job URLs conservatively by removing obvious tracking parameters while preserving job-identifying parameters.
- [ ] Store `Captured URL` when it differs from canonical `Job URL`.
- [ ] Prefer selected text as the highest-confidence source for Job Content.
- [ ] Fall back to current rendered page evidence when no selected text is present.
- [ ] Parse deterministic sources first: JSON-LD, Open Graph, page title, visible text, semantic HTML, and simple heuristics.
- [ ] Add an adapter hook for future site-specific extraction, but do not require adapters for MVP success.
- [ ] Optionally call an LLM only when deterministic parsing is incomplete or low-confidence.
- [ ] Require LLM fallback to leave unknown values missing rather than inventing company, title, location, or content.
- [ ] Return `needs_review` when required creation fields are missing or confidence is low.

## Phase 5: Notion Page Body

- [ ] Write a capture summary block with source URL, captured timestamp, and parsing notes when useful.
- [ ] Write Job Content as readable Notion blocks, not a single text dump.
- [ ] Preserve source headings when present.
- [ ] Preserve paragraphs and bullet lists where possible.
- [ ] Preserve compensation in Job Content, not as dedicated MVP properties.
- [ ] Preserve Location as display text, not normalized geography/workplace fields.
- [ ] Do not store raw HTML or DOM dumps in Notion by default.
- [ ] Batch block appends to stay within Notion API limits.
- [ ] Add an explicit truncation note if content exceeds the project-defined cap.

## Phase 6: Chrome Extension

- [ ] Use `activeTab` and `scripting`; do not request broad persistent host permissions for MVP.
- [ ] Open the capture UI as a persistent Chrome side panel instead of a focus-losing popup.
- [ ] Capture only after explicit user button click.
- [ ] Read the current rendered Source Page state; do not click expanders, switch tabs, scrape linked pages, or operate the job site.
- [ ] Gather current URL, page title, selected text, visible text, semantic HTML, and discovered page metadata.
- [ ] Store only extension-needed config: backend URL and capture token.
- [ ] Never store Notion token or Notion database ID in the extension.
- [ ] Show backend status using the backend health/config endpoint.

## Phase 7: Side Panel States

- [ ] `Created`: show Notion page link plus parsed title, company, and location.
- [ ] `Already captured`: show existing Notion page link.
- [ ] `Needs review`: show editable parsed fields and a create/confirm action.
- [ ] `Failed`: show a specific reason and next action.
- [ ] Show `Backend offline` with configured localhost URL and a start-service hint.
- [ ] Avoid rendering the full Job Content in the side panel.
- [ ] Prompt the user to expand hidden sections and retry when captured content appears too short.

## Phase 8: Tests And Fixtures

- [ ] Unit test URL canonicalization, including tracking params and job-identifying params.
- [ ] Unit test Notion schema validation with valid, missing, and wrong-type properties.
- [ ] Unit test duplicate detection behavior by canonical Job URL.
- [ ] Unit test Notion property mapping and capture defaults.
- [ ] Unit test Notion block conversion, batching, and truncation notes.
- [ ] Unit test parser behavior with selected text, no selection, metadata-rich pages, and weak pages.
- [ ] Unit test that unknown parsed fields stay missing rather than invented.
- [ ] Test capture endpoint token enforcement and CORS behavior.
- [ ] Test extension capture extraction against saved HTML fixtures.
- [ ] Add at least one end-to-end local happy path with a mocked Notion client.

## Manual Acceptance Checklist

- [ ] With backend offline, clicking capture shows a backend-offline failure and does not write to Notion.
- [ ] With invalid Notion schema, the side panel reports schema invalid and does not create a page.
- [ ] With selected job description text, capture creates a readable Notion page.
- [ ] With no selection on a clean job page, capture creates a readable Notion page.
- [ ] Re-capturing the same canonical Job URL returns the existing Notion page.
- [ ] A low-confidence capture enters review instead of silently creating a poor record.
- [ ] A long posting is stored in batched blocks or explicitly marked as truncated.

## Out Of Scope For MVP

- Managing or mutating the Notion database schema.
- Local durable storage, sync, or retry queues.
- Broad site-specific job board adapter suite.
- Normalized location, workplace type, region, compensation, or salary fields.
- Application workflow automation after initial capture defaults.
- Match scoring.
- Raw HTML archival in Notion.
