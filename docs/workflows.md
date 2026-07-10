# Workflows

This guide describes how Merida behaves from the operator's point of view and how each workflow maps to backend behavior.

## Daily Operator Sequence

1. Start the app with `npm start`.
2. Use the Chrome side panel to capture one or more job postings into Notion.
3. Open `http://127.0.0.1:3217/analysis`.
4. Run Job Posting Analysis for a small batch.
5. Open `http://127.0.0.1:3217/resumes`.
6. Create a resume for each ready posting.
7. Review the Job-Specific Resume, the related Resume Fit Analysis Note, and the local PDF.

## Job Posting Capture

The Chrome extension lives in `src/features/jobPostings/extension`.

### Direct Capture

Use **Capture Current Page** when the page is readable and the inferred fields look likely to be correct.

Backend path:

1. The side panel collects evidence from all frames in the active tab.
2. The extension sends the evidence to `POST /capture` with `X-Capture-Token`.
3. The backend parses the evidence into a Job Posting candidate.
4. The backend validates the Job Postings database schema.
5. The backend checks for an existing page with the canonical `Job URL`.
6. The backend writes a new Notion page when required fields and confidence are sufficient.

Possible results:

| Result | Meaning |
| --- | --- |
| `created` | A new Job Posting page was written to Notion. |
| `already_captured` | A page with the same canonical Job URL already exists. |
| `needs_review` | Parsed fields are incomplete or confidence is low. |
| `failed` | Configuration, schema, content, token, or Notion write failed. |

### Fill Form And Confirm

Use **Fill Form** when the page needs review or when you want to inspect the parsed content before writing.

Backend path:

1. The extension collects the same page evidence.
2. The extension sends it to `POST /parse`.
3. The backend parses fields but does not read or write Notion.
4. The extension fills the editable review form.
5. The user edits fields.
6. The extension sends reviewed fields to `POST /confirm`.
7. The backend validates schema, deduplicates, and writes the Notion page.

`/confirm` still requires minimum creation fields:

- Job Posting title
- Job URL
- Job Content
- Company Name
- Job Title
- Location

### Job Posting Page Body

Created Job Posting pages contain:

- `Capture Summary`
- `Job Content`

`Job Content` is the source section used by later analysis and resume generation.

## Job Posting Analysis

The analysis UI is served at:

```text
http://127.0.0.1:3217/analysis
```

### Eligibility

A Job Posting is in the Analysis Queue when:

- `Application Status` is `To Apply`.
- `Analyzed` is unchecked.

If a page already contains a `Job Posting Analysis` section but the checkbox is unchecked, the workflow repairs the checkbox instead of duplicating analysis.

### Status Check

`GET /analysis/status` checks:

- Base config validity.
- Whether `DEEPSEEK_API_KEY` is present.
- Job Postings database schema validity.
- Current queue count.
- Selected DeepSeek model.

The Run button is disabled when analysis is not configured.

### Batch Run

`POST /analysis/run` accepts:

```json
{ "limit": 5 }
```

The limit is normalized to the range `1` through `25`; the default is `5`.

The response streams NDJSON events:

```json
{"type":"run_started","requested":5,"total":2,"model":"deepseek-v4-flash"}
{"type":"item_started","index":1,"total":2,"item":{"id":"...","title":"..."}}
{"type":"item_finished","index":1,"total":2,"item":{"id":"...","title":"..."},"result":{"status":"analyzed","message":"Analysis appended and Analyzed checkbox checked."}}
{"type":"run_finished","requested":5,"total":2,"totals":{"analyzed":1,"skipped":0,"failed":0,"repaired":1}}
```

Each Job Posting is isolated. One failed posting does not stop the rest of the batch.

### Analysis Output

The backend asks DeepSeek for strict JSON containing:

- A three-sentence summary.
- Grouped Skill Signals.

The validator rejects:

- Empty DeepSeek content.
- Non-JSON responses.
- Summaries that are not exactly three non-empty sentences.
- Skill Signals without names or evidence.
- Skill Signal evidence not supported by Job Content.
- Generic traits that are not concrete Skill Signals.

Saved Notion output is appended under:

- `Job Posting Analysis`
- `Summary`
- `Skill Signals`

The backend appends analysis blocks before marking `Analyzed` true.

## Resume Creation

The resume UI is served at:

```text
http://127.0.0.1:3217/resumes
```

### Eligibility

A Job Posting appears in the Resume Creation Queue when:

- `Application Status` is `To Apply`.
- `Analyzed` is checked.
- The `Resumes` relation is empty.

The page must also have Company Name and Job Title so Merida can build a Resume Name:

```text
{Job Title} at {Company Name}
```

### Status Check

`GET /resumes/status` checks:

- Base config validity.
- `NOTION_RESUME_DATABASE_ID`.
- `NOTION_NOTES_DATABASE_ID`.
- `DEEPSEEK_API_KEY`.
- `FIT_RUNTIME_URL`.
- Resume workflow schema validity.
- Notes workflow schema validity.
- Python fit runtime health.
- Current resume queue items.

If the Python runtime is unavailable, the page is blocked with:

```text
Resume Fit Analysis runtime is unavailable. Start it with npm start.
```

### Create Resume

The UI sends:

```json
{ "jobPostingPageId": "..." }
```

to `POST /resumes/create`.

The backend then:

1. Reads the Job Posting page.
2. Returns `already_exists` if a related Resume is already present.
3. Validates config and schemas.
4. Confirms the posting is still ready for resume creation.
5. Recursively reads the Job Posting blocks.
6. Extracts `Job Content` and `Job Posting Analysis`.
7. Finds exactly one Resume page named `Master Resume`.
8. Recursively reads Master Resume blocks.
9. Extracts Master Resume Evidence Items.
10. Extracts Fit Requirements with DeepSeek.
11. Validates requirement evidence against Job Content.
12. Requests candidate matches and scoring from the Python runtime.
13. Fails before writing if evidence support is insufficient.
14. Generates an application-ready resume with DeepSeek.
15. Filters, repairs, and completes resume bullets from supported Master Resume evidence.
16. Writes an unlinked Job-Specific Resume page.
17. Writes a related Resume Fit Analysis Note.
18. Saves a local PDF.
19. Attaches the Resume to the Job Posting.

### Successful Output

On success, the UI shows:

- A link to the created Resume.
- A link to the related Resume Fit Analysis Note.
- The relative PDF path, such as `export/Amplify-ElizabethParnell.pdf`.

The Resume page contains only employer-facing resume content:

- Candidate name and contact line from the resume template.
- Summary.
- Preserved work-experience roles.
- Evidence-backed bullets.

The Resume Fit Analysis Note contains the supporting analysis:

- Fit Score.
- Category coverage.
- Requirement Evidence Map.
- Gaps.
- Generation Guardrails.

### Failure And Cleanup

Resume creation may fail before any writes when:

- Job Content is missing.
- Job Posting Analysis is missing.
- No Master Resume exists.
- More than one Master Resume exists.
- Master Resume evidence is empty.
- Master Resume evidence is insufficient.
- Required template roles cannot be found.
- A role has fewer than five bullet evidence items.
- DeepSeek generation fails or returns unsupported claims.

If a failure happens after a draft write begins, Merida attempts cleanup:

- Remove the local PDF if it was created.
- Archive the Note if it was created.
- Archive the draft Resume if it was created.

## PDF Export

PDFs are written to:

```text
export/{CompanyName}-ElizabethParnell.pdf
```

The export renderer is implemented in `src/features/resumes/lib/pdfExport.js`. It converts Notion-like resume blocks into a simple local PDF without a browser or external PDF dependency.

## Recommended Operating Habits

- Run small analysis batches first, usually `5`.
- Review captured Job Content in Notion before running analysis on unusual pages.
- Restart `npm start` after changing backend code, Python fit code, or the skill normalization dictionary.
- Treat `insufficient_master_resume_evidence` as a signal to inspect Master Resume evidence before relaxing guardrails.
- Keep the extension token local and rotate it if it is accidentally shared.

