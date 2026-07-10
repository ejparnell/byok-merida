# Operations And Troubleshooting

This guide covers local setup, verification, and common failure modes.

## Local Setup Checklist

1. Copy `.env.example` to `.env`.
2. Fill in Notion IDs and tokens.
3. Fill in `CAPTURE_TOKEN`.
4. Load the Chrome extension from `src/features/jobPostings/extension`.
5. Set `EXTENSION_ORIGIN` to the installed extension origin.
6. Set `DEEPSEEK_API_KEY` for analysis and resume generation.
7. Run `npm run setup:ml`.
8. Start the app with `npm start`.
9. Save backend URL and capture token in the extension options page.

## Health Checks

Backend health:

```sh
curl -H "X-Capture-Token: <capture-token>" http://127.0.0.1:3217/health
```

Backend plus Job Postings schema:

```sh
curl -H "X-Capture-Token: <capture-token>" http://127.0.0.1:3217/health?validate=1
```

Analysis readiness:

```sh
curl http://127.0.0.1:3217/analysis/status
```

Resume readiness:

```sh
curl http://127.0.0.1:3217/resumes/status
```

Python fit runtime:

```sh
curl http://127.0.0.1:3218/health
```

## Running Tests

Full test suite:

```sh
npm test
```

Focused Node tests:

```sh
node --test src/backend/test/*.test.js
node --test src/features/jobPostings/test/*.test.js
node --test src/features/resumes/test/*.test.js
node --test src/features/notes/test/*.test.js
```

Focused Python tests:

```sh
python3 -m unittest discover -s src/features/resumes/ml/test
```

Some sandboxed environments block local server binding and can fail backend server tests with `listen EPERM`. When that happens, verify the same command in an environment that permits localhost binding before changing server logic.

## Restart Rules

Restart `npm start` after changing:

- `src/backend/*`
- any feature backend route or service
- `.env`
- `src/features/resumes/ml/analysis.py`
- `src/features/resumes/ml/server.py`
- `src/features/resumes/data/skill-normalization.json`

The Python runtime loads the normalization dictionary at startup. A running runtime will not pick up dictionary changes until restarted.

## Chrome Extension Setup

1. Open `chrome://extensions`.
2. Enable Developer Mode.
3. Choose **Load unpacked**.
4. Select `src/features/jobPostings/extension`.
5. Copy the generated extension ID.
6. Set `.env`:

   ```text
   EXTENSION_ORIGIN=chrome-extension://<extension-id>
   ```

7. Restart `npm start`.
8. Open the extension options page.
9. Save:

   ```text
   Backend URL: http://127.0.0.1:3217
   Capture token: <same value as CAPTURE_TOKEN>
   ```

For local development, `src/features/jobPostings/extension/local-config.js` can provide fallback backend URL and token values before Chrome storage is saved. Use `local-config.example.js` as the template. Do not commit local tokens.

## Common Capture Issues

### Backend Offline

Symptoms:

- Extension says backend is offline.
- Capture buttons fail before parsing.

Checks:

- Confirm `npm start` is running.
- Confirm the extension backend URL matches `PORT`.
- Check `http://127.0.0.1:3217/health` with `X-Capture-Token`, or use the extension status check.

### Capture Token Missing Or Invalid

Symptoms:

- Extension says capture token is missing.
- Backend returns `invalid_token`.

Checks:

- `CAPTURE_TOKEN` is set in `.env`.
- Extension options have the exact same token.
- Restart the backend after editing `.env`.

### Origin Not Allowed

Symptoms:

- Backend returns `Request origin is not allowed.`

Checks:

- Copy the current extension ID from `chrome://extensions`.
- Confirm `.env` has the exact value:

  ```text
  EXTENSION_ORIGIN=chrome-extension://<extension-id>
  ```

- Restart the backend.

### Needs Review

`needs_review` is not a failure. It means parsing confidence is low or required fields are missing. Use the review form, edit fields, and submit **Create In Notion**.

### Missing Job Content

Symptoms:

- Capture fails with `missing_job_content`.

Checks:

- Select the job description text on the page and try Capture again.
- Use Fill Form and paste cleaned job content manually.
- Inspect console logs when `DEBUG_CAPTURE=1`.

## Common Analysis Issues

### Analysis Disabled

Symptoms:

- `/analysis` shows Analysis as missing.
- Run button is disabled.

Checks:

- Set `DEEPSEEK_API_KEY`.
- Confirm `DEEPSEEK_MODEL` is `deepseek-v4-flash` or `deepseek-v4-pro`.
- Restart the backend.

### Empty Queue

Checks:

- Job Posting `Application Status` is exactly `To Apply`.
- `Analyzed` is unchecked.
- The posting is in the configured Job Postings database.

### Analysis Section Exists But Checkbox Is False

The batch runner should repair this by checking `Analyzed`. If repair fails, inspect Notion permissions and the `Analyzed` property type.

### DeepSeek JSON Or Evidence Validation Failure

Symptoms:

- Item result is `failed`.
- Logs mention invalid JSON, empty content, or evidence not found.

Checks:

- Review the extracted Job Content in logs.
- Set `DEBUG_ANALYSIS_CONTENT=1` only while debugging and avoid sharing logs with private job content.
- Check whether the Job Content section is clean and complete.

## Common Resume Issues

### Resume Page Is Blocked

Symptoms:

- `/resumes` status is blocked.

Checks:

- `NOTION_RESUME_DATABASE_ID` is set.
- `NOTION_NOTES_DATABASE_ID` is set.
- `DEEPSEEK_API_KEY` is set.
- `FIT_RUNTIME_URL` is set.
- `npm start` is running both Node and Python.
- `curl http://127.0.0.1:3218/health` returns `ok: true`.

### Empty Resume Queue

Checks:

- Job Posting `Application Status` is exactly `To Apply`.
- `Analyzed` is checked.
- `Resumes` relation is empty.
- Company Name and Job Title are present.

### Missing Job Content

Resume creation reads the `Job Content` section from the Job Posting page body. If the section is missing or renamed, resume creation fails.

### Missing Job Posting Analysis

Resume creation requires the `Job Posting Analysis` section. Run `/analysis` before creating a resume.

### Missing Or Duplicate Master Resume

The Resumes database must contain exactly one page named `Master Resume`.

### Insufficient Master Resume Evidence

Symptoms:

- Failure reason: `insufficient_master_resume_evidence`.
- Message reports supported required/responsibility requirement counts.

What it means:

- Merida found job requirements that cannot be supported with direct or adjacent Master Resume evidence.
- The workflow is intentionally failing before writing a misleading resume.

Checks:

- Inspect the Resume Fit Analysis failure summary if present.
- Confirm Master Resume sections and bullets contain concrete evidence for the job's required responsibilities.
- Confirm role headings match the configured template roles.
- Confirm each work-experience role has at least five bullet evidence items.
- Restart the Python fit runtime after changing `skill-normalization.json`.

### Generated Resume Role Has Too Few Bullets

Each configured work-experience role needs at least five source bullet evidence items. Add evidence to the Master Resume role before retrying.

### PDF Not Created

The PDF is created after the Resume and Note write path starts. If PDF creation fails, Merida attempts to archive the draft Resume and Note. Check filesystem write access to `export/`.

## Logs

Capture logs use:

```text
[job-capture]
```

Analysis logs use:

```text
[job-analysis]
```

The Python runtime logs requests only when:

```text
FIT_RUNTIME_DEBUG=1
```

## Safe Debugging Practices

- Do not paste `.env` contents into docs or bug reports.
- Prefer `.env.example` for documenting config shape.
- Use `DEBUG_ANALYSIS_CONTENT=1` only temporarily.
- Remove temporary debug logs before finishing code changes.
- Restart both Node and Python runtimes before retrying live resume creation after code changes.
