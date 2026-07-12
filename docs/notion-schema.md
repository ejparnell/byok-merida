# Notion Schema

Merida expects existing Notion databases. It validates the configured databases before writes, but it does not create, rename, or mutate database properties.

## Database Overview

| Database     | Env var                     | Purpose                                                 |
| ------------ | --------------------------- | ------------------------------------------------------- |
| Applications | `NOTION_DATABASE_ID`        | Captured application record.                            |
| Resumes      | `NOTION_RESUME_DATABASE_ID` | One `Master Resume` and generated Job-Specific Resumes. |
| Notes        | `NOTION_NOTES_DATABASE_ID`  | App-created Resume Fit Analysis notes.                  |

## Applications Database

Required workflow properties:

The final app keeps the existing physical property names. Canonical code/domain names are translated by the Notion compatibility adapter.

| Physical property    | Canonical name     | Type      | Required behavior                                                                              |
| -------------------- | ------------------ | --------- | ---------------------------------------------------------------------------------------------- |
| `Job Posting`        | Application        | title     | Page title for a specific role, `{Role} at {Company Name}`.                                    |
| `Company Name`       | Company Name       | rich text | Used for queue display and PDF file naming.                                                    |
| `Job Title`          | Role               | rich text | Used for queue display and Resume Name creation.                                               |
| `Job URL`            | Job URL            | URL       | Canonical URL used for duplicate detection.                                                    |
| `Application Date`   | Date Found         | date      | When application was captured.                                                                 |
| `Application Status` | Application Status | select    | Workflow state. Capture sets new Applications to `To Apply`.                                   |
| `Analyzed`           | Analyzed           | checkbox  | Marks whether Application Analysis has been completed.                                         |
| `Match Score`        | Match Score        | number    | High-level job/application fit score written by Application Analysis. Capture does not set it. |

Optional Notion-managed properties:

| Property               | Type      | Optional behavior                                           |
| ---------------------- | --------- | ----------------------------------------------------------- |
| `Location`             | rich text | Display text captured from the source page.                 |
| `Work Type`            | select    | Remote, hybrid, onsite                                      |
| `Employment Type`      | select    | Full-time, Part-time, Contract, Internship, Freelance       |
| `Salary Range`         | rich text | Posted salary expectation for the role.                     |
| `Application Deadline` | date      | When the application needs to be submitted by.              |
| `Next Step Date`       | date      | Upcoming interview, follow-up date, or reminder.            |
| `Last Contacted`       | date      | Last email, call, LinkedIn message, application submission. |

Missing optional management properties must not block capture, Application Analysis, Resume Creation, or dashboard readiness.

Select values:

**Application Status**:

- To Apply
- Applied
- Rejected
- Not Interested
- Archived

**Work Types**:

- Remote
- Hybrid
- Onsite

**Employment Types**:

- Full-time
- Part-time
- Contract
- Internship
- Freelance

Required relations for the full workflow:

| Property  | Type     | Target           | Inverse name  |
| --------- | -------- | ---------------- | ------------- |
| `Resumes` | relation | Resumes database | `Application` |
| `Notes`   | relation | Notes database   | `Application` |

### Application Page Body

Successful extension capture requires readable job content and writes these sections:

- `Capture Summary`
- `Job Content`

Manually created Notion Applications may exist without `Job Content`, but they are not eligible for Application Analysis until the body contains readable `Job Content`.

Analysis appends:

- `Application Analysis`
  - `Summary`
  - `Match Score`
  - `Skill Signals`

The body stores the same deterministic `Match Score` written to the database property. Persisting it in the body lets the backend recover the exact score if the body write succeeds but the final property update fails.

After writing the `Application Analysis` body, Application Analysis sets `Match Score` and `Analyzed = true` as its final commit. If an Application already has a readable `Application Analysis` section but `Analyzed = false`, the backend repairs the properties without rerunning the LLM. For a legacy analysis body without a stored score, it may recompute the score deterministically; if recovery is impossible, it leaves `Match Score` empty.

Resume creation reads `Job Content` and `Application Analysis` from the page body. Both must be readable before an Application can create a Job-Specific Resume.

## Resumes Database

Required properties:

| Property      | Type     | Required behavior                                                                                 |
| ------------- | -------- | ------------------------------------------------------------------------------------------------- |
| `Name`        | title    | `Master Resume` for the source resume, or `{Role} at {Company Name}` for generated resumes.       |
| `Job Posting` | relation | Must target the Applications database. The Applications inverse relation must be named `Resumes`. |

Required relation for Notes:

| Property | Type     | Target         | Inverse name |
| -------- | -------- | -------------- | ------------ |
| `Notes`  | relation | Notes database | `Resume`     |

### Master Resume Requirements

The Resumes database must contain exactly one page named:

```text
Master Resume
```

The Master Resume body is the evidence source for generated resumes. Merida extracts evidence from:

- headings
- paragraphs
- quote blocks
- callouts
- bulleted list items
- numbered list items

Health checks validate general Master Resume readiness only:

- exactly one `Master Resume` page exists
- the body is readable
- at least one work-experience section is recognizable
- some bullet evidence can be extracted

Application-specific evidence sufficiency is checked during Resume Creation, not during health checks.

Work-experience sections are used as the template for generated Job-Specific Resumes. Generated resumes preserve every configured work-experience role from the Master Resume. Work-experience bullets are customized based on the target `Job Content`, `Application Analysis`, and matching results, while remaining evidence-backed and truthful.

Each generated work-experience role should target 5 to 7 evidence-backed bullets, with 6 preferred, when enough supporting evidence exists. The fit gate blocks generation when the Master Resume evidence cannot truthfully support the target Application.

Work experience is a required section, but the Master Resume can have other sections including but not limited to:

- Education
- Volunteer Work
- Certifications

### Job-Specific Resume Body

Generated Job-Specific Resumes contain employer-facing resume content only:

- name and contact line from the Master Resume
- summary
- configured work-experience roles
- evidence-backed bullets
- education, volunteer work, certifications, and other preserved Master Resume sections

Non-work-experience sections from the Master Resume are preserved semantically unchanged. The renderer may normalize formatting for Notion and PDF output, but the LLM must not rewrite, summarize, embellish, or target-tailor those sections.

Resume Fit Analysis, evidence traces, gaps, and guardrails are stored in a related Note, not in the Resume body.

## Notes Database

For v1, Notes are app-created Resume Fit Analysis Notes only. Merida does not provide a general notes system or a notes editor.

Required properties:

| Property      | Type     | Required behavior                                                                               |
| ------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `Name`        | title    | For resume fit notes: `Resume Fit Analysis - {Role} at {Company Name}`.                         |
| `Application` | relation | Must target the Applications database. The Applications inverse relation must be named `Notes`. |
| `Resume`      | relation | Must target the Resumes database. The Resumes inverse relation must be named `Notes`.           |

### Resume Fit Analysis Note Body

Resume creation writes a related Note containing:

- `Resume Fit Analysis`
- `Summary`
- `Fit Score`
- `Category Coverage`
- `Requirement Evidence Map`
- `Gaps`
- `Generation Guardrails`

The Note is related to both the Application and the generated Resume.
