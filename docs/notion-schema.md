# Notion Schema - Current

Merida expects existing Notion databases. It validates the configured databases before writes, but it does not create, rename, or mutate database properties.

## Database Overview

| Database | Env var | Purpose |
| --- | --- | --- |
| Job Postings | `NOTION_DATABASE_ID` | Captured job postings, Job Content, Job Posting Analysis, application readiness, inverse Resume and Note relations. |
| Resumes | `NOTION_RESUME_DATABASE_ID` | One `Master Resume` and generated Job-Specific Resumes. |
| Notes | `NOTION_NOTES_DATABASE_ID` | Supporting notes, especially Resume Fit Analysis Notes. |

## Job Postings Database

Required properties:

| Property | Type | Required behavior |
| --- | --- | --- |
| `Job Posting` | title | Page title for a specific role, usually `{Job Title} at {Company Name}`. |
| `Company Name` | rich text | Used for queue display and PDF file naming. |
| `Job Title` | rich text | Used for queue display and Resume Name creation. |
| `Job URL` | URL | Canonical URL used for duplicate detection. |
| `Location` | rich text | Display text captured from the source page. |
| `Application Status` | select | Must include a `To Apply` option. |
| `Match Score` | number | Reserved for match scoring. Capture does not set it. |
| `Application Date` | date | Reserved for application workflow. Capture does not set it. |
| `Analyzed` | checkbox | Marks whether Job Posting Analysis has been completed. |

Optional property:

| Property | Type | Behavior |
| --- | --- | --- |
| `Captured URL` | URL | Stores the exact browser URL when it differs from the canonical Job URL. |

Required relations for the full workflow:

| Property | Type | Target | Inverse name |
| --- | --- | --- | --- |
| `Resumes` | relation | Resumes database | `Job Posting` |
| `Notes` | relation | Notes database | `Job Posting` |

### Job Posting Page Body

Capture writes these sections:

- `Capture Summary`
- `Job Content`

Analysis appends:

- `Job Posting Analysis`
  - `Summary`
  - `Skill Signals`

Resume creation reads `Job Content` and `Job Posting Analysis` from the page body.

## Resumes Database

Required properties:

| Property | Type | Required behavior |
| --- | --- | --- |
| `Name` | title | `Master Resume` for the source resume, or `{Job Title} at {Company Name}` for generated resumes. |
| `Job Posting` | relation | Must target the Job Postings database. The Job Postings inverse relation must be named `Resumes`. |

Required relation for Notes:

| Property | Type | Target | Inverse name |
| --- | --- | --- | --- |
| `Notes` | relation | Notes database | `Resume` |

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

Work-experience sections must match the configured resume template roles in `src/features/resumes/lib/resumeTemplate.js`:

| Role | Organization | Date range |
| --- | --- | --- |
| Software Engineer | ClinMatchGO | 2025 - Present |
| AI Studio Coach | Break Through Tech | 2025 - Present |
| Lead Instructor | General Assembly | 2021 - 2024 |
| Software Engineer | Wayfair | 2018 - 2021 |

Each matched work-experience role must have at least five bullet evidence items. Generated resumes preserve every configured work-experience role and target 5 to 7 evidence-backed bullets per role, with 6 preferred.

### Job-Specific Resume Body

Generated Job-Specific Resumes contain employer-facing resume content only:

- name and contact line from the resume template
- summary
- configured work-experience roles
- evidence-backed bullets

Resume Fit Analysis is stored in a related Note, not in the Resume body.

## Notes Database

Required properties:

| Property | Type | Required behavior |
| --- | --- | --- |
| `Name` | title | For resume fit notes: `Resume Fit Analysis - {Job Title} at {Company Name}`. |
| `Job Posting` | relation | Must target the Job Postings database. The Job Postings inverse relation must be named `Notes`. |
| `Resume` | relation | Must target the Resumes database. The Resumes inverse relation must be named `Notes`. |

### Resume Fit Analysis Note Body

Resume creation writes a related Note containing:

- `Resume Fit Analysis`
- `Summary`
- `Fit Score`
- `Category Coverage`
- `Requirement Evidence Map`
- `Gaps`
- `Generation Guardrails`

The Note is related to both the Job Posting and the generated Resume.

## Relation Validation

Merida validates relation targets with `src/lib/notionRelations.js`.

The validator accepts relation targets returned as:

- `relation.database_id`
- `relation.data_source_id`
- the configured database ID
- the database ID returned by Notion
- IDs listed in returned Notion `data_sources`

It also validates inverse relation names when Notion returns them. For example, the Resume database property `Job Posting` must point to the Job Postings database, and its inverse on the Job Postings database must be named `Resumes`.

## Queue Rules

### Analysis Queue

A Job Posting is eligible for Job Posting Analysis when:

- `Application Status = To Apply`
- `Analyzed = false`

### Resume Creation Queue

A Job Posting is eligible for Resume Creation when:

- `Application Status = To Apply`
- `Analyzed = true`
- `Resumes` relation is empty

## Schema Validation Endpoints

Use:

```sh
curl -H "X-Capture-Token: <capture-token>" http://127.0.0.1:3217/health?validate=1
```

to validate base config and the Job Postings schema.

Use:

```sh
curl http://127.0.0.1:3217/analysis/status
curl http://127.0.0.1:3217/resumes/status
```

to validate workflow-specific readiness.

`/resumes/status` validates Job Postings, Resumes, Notes, and the Python fit runtime.
