# Job Postings

This feature captures the current rendered job posting page from a local Chrome extension side panel and writes it into an existing Notion database through the app-level Local Operator backend.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Set `NOTION_TOKEN`, `NOTION_DATABASE_ID`, optional `NOTION_RESUME_DATABASE_ID`, optional `NOTION_NOTES_DATABASE_ID`, `CAPTURE_TOKEN`, `PORT`, and the Resume Fit Analysis settings when using `/resumes`.
3. Load the unpacked extension from `src/features/jobPostings/extension` in Chrome.
4. Copy the extension ID from `chrome://extensions`.
5. Set `EXTENSION_ORIGIN=chrome-extension://<extension-id>` in `.env`.
6. Start the Local Operator backend with `npm start`.
7. Open the extension options page and save the backend URL plus the same `CAPTURE_TOKEN`.

For local development, the unpacked extension also reads `extension/local-config.js` as a fallback when Chrome extension storage has not been saved yet. This file is ignored by git and should contain only the backend URL and local capture token. Use `extension/local-config.example.js` as the template.

## Expected Notion Schema

- `Job Posting` - title
- `Company Name` - rich text
- `Job Title` - rich text
- `Job URL` - URL
- `Captured URL` - URL, optional
- `Location` - rich text
- `Application Status` - select with a `To Apply` option
- `Match Score` - number
- `Application Date` - date
- `Analyzed` - checkbox

The backend validates this schema before capture writes. It does not create or mutate Notion properties.

## Local Operator Endpoints

- `GET /analysis` serves the local Job Posting Analysis interface.
- `GET /analysis/status` checks analysis config, schema, and the To Apply queue count.
- `POST /analysis/run` starts a token-protected sequential analysis batch.
- `GET /resumes` serves the local Resume Creation interface.
- `GET /resumes/status` checks resume config, both Notion schemas, and the ready resume queue.
- `POST /resumes/create` creates or returns the generated Resume for a selected Job Posting.
- `GET /health?validate=1` checks backend config and, when requested, the Notion schema.
- `POST /capture` accepts Capture Evidence from the extension and returns a Capture Result.
- `POST /parse` accepts Capture Evidence from the extension and returns parsed fields for review without reading or writing Notion.
- `POST /confirm` accepts reviewed parsed fields and creates the Notion page.

Capture endpoints require `X-Capture-Token`. The static `/analysis` page does not contain secrets and can be opened directly; its same-origin analysis calls are handled by the Local Operator backend without exposing Notion or DeepSeek credentials in the browser.

## Analysis Setup

Set `DEEPSEEK_API_KEY` to enable Job Posting Analysis. `DEEPSEEK_MODEL` defaults to `deepseek-v4-flash` and can be set to `deepseek-v4-pro` when desired. Do not use the deprecated `deepseek-chat` or `deepseek-reasoner` aliases. Capture endpoints remain usable when DeepSeek is not configured.

Analysis logs include extracted Job Content length and previews plus DeepSeek request/response metadata. Set `DEBUG_ANALYSIS_CONTENT=1` only when you need full extracted Job Content logged for debugging.

Analysis storage is concentrated in the feature-owned Job Posting Analysis Store module. The batch runner asks that module for readiness, queue items, analysis input, and saved findings; the module owns the Notion details for Job Content reads, append-before-marking, and analyzed-checkbox repair.

## Resume Setup

Set `NOTION_RESUME_DATABASE_ID` and `NOTION_NOTES_DATABASE_ID` to enable the `/resumes` interface. The Resume database must already exist in Notion with a `Name` title property and a `Job Posting` relation to the Job Posting database. The Job Posting database must expose the inverse relation as `Resumes`.

The Notes database must already exist in Notion with a `Name` title property, a `Job Posting` relation to the Job Posting database, and a `Resume` relation to the Resume database. Both the Job Posting and Resume databases must expose the inverse relation as `Notes`.

The `/resumes` interface now requires the local Resume Fit Analysis runtime and DeepSeek generation config before enabling `Create Resume`. Run `npm run setup:ml` once to create the local Python environment, then `npm start` starts both the Node backend and the Python fit runtime. Semantic similarity is computed locally by the Python runtime, so no paid embedding provider is required.

Resume generation reads `Job Content`, `Job Posting Analysis`, and exactly one `Master Resume` page from the Resume database. It writes a clean Job-Specific Resume body to the Resume page, writes the `Resume Fit Analysis` section to a related Note, saves a local PDF export at `export/{CompanyName}-ElizabethParnell.pdf`, and attaches the Resume to the Job Posting only after all writes succeed.

## Extension Behavior

The extension opens as Chrome's right-side panel from the toolbar action so it can stay visible while the user clicks back into the Source Page. It uses `activeTab` and `scripting`, captures only after a button click, and sends per-frame Capture Evidence with the active tab URL to the local backend. The backend-owned Capture Evidence module merges frames, normalizes selected text, visible text, semantic HTML, and page metadata, and treats selected text as the highest-confidence source for Job Content. The side panel can either capture directly into Notion or fill the editable review form from the current page without saving; only the direct capture and reviewed confirm actions can create Notion pages.

## Verification

Run:

```sh
npm test
```

The test suite covers URL canonicalization, Capture Evidence normalization, parsing, Notion schema/property mapping, Notion block conversion, capture orchestration, and local backend endpoint behavior.
