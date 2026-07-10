# Local backend owns parsing and Notion writes

The Chrome extension captures job posting evidence from the active Source Page, then sends that evidence to a local backend service. The backend owns parsing, Notion API writes, integration secrets, retries, duplicate detection, and future enrichment such as match scoring, because keeping those responsibilities out of the extension reduces credential exposure and gives the capture pipeline a testable server-side boundary.

The extension sends structured Capture Evidence rather than only raw HTML or only plain text. The payload can include the current URL, page title, selected text, visible text, semantic HTML, and discovered page metadata so the backend has enough evidence to parse fields without making the extension responsible for the final Job Posting shape.

When selected text is present, the backend treats it as the highest-confidence source for Job Content. When the user has not selected text, the backend falls back to automatic extraction from the full Capture Evidence payload.

After parsing, the backend uses confidence-gated creation. High-confidence captures create the Notion page immediately, while captures with missing required fields or low confidence return a Capture Review for user confirmation instead of silently creating a poor record.

Capture confidence remains internal for MVP. It controls whether the backend returns a created or needs-review result, and low-confidence details may appear as parsing notes, but confidence is not stored as a Notion property.

A Job Posting can be created when it has a Job Posting Title, Job URL, and Job Content. Company Name, Job Title, and Location are valuable parsed fields, but they are best-effort metadata rather than minimum creation requirements.

The canonical Job URL is the duplicate key for captured postings. When a Duplicate Capture is detected, the backend returns the existing Notion page link instead of creating a second page or automatically updating the existing one.

Job URL canonicalization is conservative. The backend removes common tracking parameters and obvious fragments, preserves job-identifying parameters unless a site-specific rule says otherwise, and keeps the Captured URL as evidence when it differs from the canonical Job URL.

Parsing is deterministic-first with optional LLM fallback. The backend first uses structured metadata, page title, readable text, semantic HTML, and heuristics; an LLM may be used only when deterministic parsing is incomplete or low-confidence, and it must leave unknown fields missing instead of inventing values.

Parsing starts generic-first. The backend may include an adapter hook for site-specific extraction, but MVP success does not depend on building an adapter suite for individual job boards; adapters should be added only after real capture examples prove they are needed.

The extension shows compact Capture Results instead of rendering the full Job Content. Supported outcomes are created, already captured, needs review, and failed; each outcome includes the parsed summary or specific failure reason needed to trust the result and continue.

When the local backend is offline, the extension shows a backend-offline failure with the configured localhost URL and a hint to start the service. It does not fall back to writing directly to Notion from the extension.

The MVP captures only the current rendered Source Page state. The extension does not click expanders, switch tabs, scrape linked pages, or otherwise operate the job site; when captured content appears too short, the Capture Result can prompt the user to expand hidden sections and retry.
