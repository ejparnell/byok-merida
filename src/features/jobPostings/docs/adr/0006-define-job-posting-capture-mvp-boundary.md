# Define job posting capture MVP boundary

The MVP is done when a local Chrome extension button captures the current rendered Source Page, sends structured Capture Evidence to a token-protected local backend, parses a Job Posting, validates the Configured Notion Database schema, prevents Duplicate Captures by canonical Job URL, and creates a readable Notion page with required properties and Job Content blocks. The MVP popup handles created, already-captured, needs-review, and failed Capture Results.

The MVP explicitly excludes Notion schema management, local durable storage, a broad job-board adapter suite, normalized location or compensation fields, application workflow automation, match scoring, and raw HTML archival.
