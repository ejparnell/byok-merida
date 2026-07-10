# Job Postings

Job Postings owns the language for captured job opportunities imported from external job description webpages into the user's Notion workspace.

## Language

**Job Posting**:
A specific employment opportunity captured from a job description webpage. A Job Posting represents one role at one source URL, not the company as a whole.
_Avoid_: Company, job description

**Application**:
The user's tracked pursuit of one Job Posting. An Application owns the pursuit state and application materials, while the related Job Posting remains the source opportunity and content. In v1, each Application corresponds to exactly one Job Posting and each Job Posting corresponds to exactly one Application.
_Avoid_: Job Posting when referring to pursuit state or application materials

**Job Posting Title**:
The title used for the Notion database item representing a Job Posting. It is stored in the `Job Posting` title property and combines the role and company, such as "{Job Title} at {Company Name}", so multiple postings from the same company remain distinguishable.
_Avoid_: Company Name

**Job URL**:
The canonical source URL used to identify a Job Posting and prevent duplicate captures. It removes obvious tracking noise while preserving parameters that may identify the posting.
_Avoid_: Captured URL, tracking URL

**Captured URL**:
The exact URL present in the browser when the Source Page is captured. It is kept as evidence when it differs from the canonical Job URL.
_Avoid_: Job URL

**Source Page**:
The external webpage where a Job Posting is found and inspected for capture. The Source Page is read as page content, DOM, or HTML, but it is not itself the stored Notion page body.
_Avoid_: Raw job content

**Capture Evidence**:
The structured page evidence gathered from a Source Page before a Job Posting is parsed. Capture Evidence can include the URL, page title, selected text, visible text, semantic HTML, and metadata, but it is not the final Job Posting record.
_Avoid_: Raw HTML dump, parsed job posting

**Job Content**:
The cleaned, human-readable content of a Job Posting that is inserted into the Notion page body. It preserves the meaningful posting information without treating the full raw DOM or HTML as the primary record.
_Avoid_: Raw HTML, page dump

**Job Posting Analysis**:
A batch enrichment workflow for already-captured Job Postings that reads the existing Notion Job Content section, appends evidence-backed analysis findings to the same Notion page body, and marks the posting as analyzed without analyzing capture metadata, prior analysis output, re-fetching the Source Page, or rerunning capture.
_Avoid_: Capture, recapture, source scraping

**Skill Signal**:
A concrete resume-tailoring signal found in Job Content, such as a technology, tool, platform, framework, database, API style, programming language, testing practice, architecture practice, workflow method, or explicit domain knowledge. Generic traits are not Skill Signals unless the posting ties them to a concrete work mode.
_Avoid_: Soft skill, personality trait, likely skill

**Analysis Findings**:
The structured output of Job Posting Analysis appended under a stable `Job Posting Analysis` section in the Notion page body. Analysis Findings contain a three-sentence summary and grouped Skill Signals.
_Avoid_: Match score, capture summary, notes dump

**Analyzed Job Posting**:
A Job Posting that has already received Analysis Findings. A Job Posting is treated as analyzed when either the required `Analyzed` checkbox property is checked or the Notion page body already contains the stable `Job Posting Analysis` section.
_Avoid_: Duplicate analysis, reanalysis

**Analysis Batch Run**:
A user-triggered Job Posting Analysis run that processes a bounded number of eligible Job Postings. Each Job Posting is an isolated unit of work, so one failed posting does not stop the rest of the run.
_Avoid_: Bulk edit, all-or-nothing analysis

**Analysis Queue**:
The eligible set of Job Postings selected for an Analysis Batch Run. The Analysis Queue contains only postings with `Application Status` set to `To Apply` and the required `Analyzed` checkbox unchecked.
_Avoid_: Saved postings, applied postings, all postings

**Analysis Result**:
The per-posting outcome reported during an Analysis Batch Run. Supported results are analyzed, skipped, failed, and repaired.
_Avoid_: Capture Result, dashboard status

**Configured Notion Database**:
The existing Notion database selected as the destination for captured Job Postings. Its schema is treated as a user-owned workspace contract that must be validated before capture writes.
_Avoid_: Generated database, managed schema

**Capture Defaults**:
The initial workflow values assigned when a Job Posting is first created in Notion. Capture Defaults mark the posting as ready to apply, leave application-specific dates and scoring fields blank, and avoid owning later application workflow changes.
_Avoid_: Application workflow, status automation

**Match Score**:
An evaluation score assigned by a future matching workflow. A blank Match Score means the Job Posting has not been scored.
_Avoid_: Capture confidence, default score

**Location**:
The location text shown by the Source Page for a Job Posting. MVP captures preserve Location as display text rather than normalizing it into workplace type, region, or geography fields.
_Avoid_: Workplace Type, Region

**Capture Review**:
A user confirmation step for a parsed Job Posting when required information is missing or the capture confidence is low.
_Avoid_: Manual entry, failed capture

**Capture Result**:
The outcome returned after a capture attempt, shown by the extension so the user can see whether a Job Posting was created, already existed, needs review, or failed.
_Avoid_: Notification, popup state

**Duplicate Capture**:
An attempted capture whose canonical Job URL already belongs to an existing Job Posting in Notion.
_Avoid_: Recapture, refresh
