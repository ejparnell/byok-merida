# Store Resume Fit Analysis in a related Note

Resume Fit Analysis is no longer written into the Job-Specific Resume page body. It is written into a related Note that connects to both the Job Posting and the Job-Specific Resume.

This supersedes ADR-0012 and ADR-0013. Those decisions kept Resume Fit Analysis visible inside the Resume page for auditability, but that made the Resume page contain both application-facing content and internal analysis. The new boundary keeps the Resume page clean: it should hold only the employer-facing Job-Specific Resume, while the Note preserves the analysis, Fit Score, gaps, and evidence details needed to audit or regenerate the resume later.

Job Posting Analysis remains on the Job Posting page because it describes the opportunity itself and powers the analyzed queue. Resume Fit Analysis remains a Resumes-owned comparison artifact, but its durable Notion home is a Note related to the correct Job Posting and Resume.

`Run Analysis` is unchanged: it only creates or updates Job Posting Analysis on the Job Posting. `Create Resume` generates the Resume Fit Analysis, stores it as a related Note, and uses that same analysis result to generate the clean Job-Specific Resume content.

`Create Resume` must fail before attaching the Resume to the Job Posting if the Resume Fit Analysis Note cannot be created or linked. The related Resume remains the durable signal that a Job Posting has a completed resume, so the workflow should attach that relation only after both the clean Resume body and the related Resume Fit Analysis Note are written. If a Note write fails after an unlinked Resume draft is created, the draft should be cleaned up or archived rather than leaving the Job Posting with a misleading completed Resume relation.

Resume Fit Analysis Notes are named `Resume Fit Analysis - {Job Title} at {Company Name}`. The name is intentionally distinct from the Job-Specific Resume's `{Job Title} at {Company Name}` name so Notion search and relation views make the analysis artifact obvious.

During the first `Create Resume` run, Resume generation uses the in-memory Resume Fit Analysis result it just produced. The workflow writes the Resume Fit Analysis Note as the durable audit record, but does not read the Note back from Notion before drafting the Resume. Later revisit or regeneration workflows may read the related Resume Fit Analysis Note.

If `Create Resume` fails after creating a Resume Fit Analysis Note but before attaching the Resume relation, v1 treats the Note as orphaned cleanup state. The workflow should archive or replace the orphaned Note during cleanup, then create a fresh Note on retry. A Note without a completed related Resume is not reusable source material yet.

`/resumes/status` must require `NOTION_NOTES_DATABASE_ID` and validate the Notes database schema before enabling `Create Resume`. Capture and `/analysis` continue working without Notes config, but `/resumes` is blocked when the Notes database is missing or when `Name`, `Job Posting`, `Resume`, or either inverse `Notes` relation is misconfigured.

There is no migration in v1 for existing Job-Specific Resume pages that already contain `Resume Fit Analysis` in the Resume body. New `Create Resume` runs write clean Resume pages plus related Notes. Existing Resume pages remain historical output until a later cleanup or regeneration workflow exists.

The v1 Resume Fit Analysis Note body uses the same visible `Resume Fit Analysis` blocks that were previously written into the Resume body. This keeps the analysis content unchanged while moving it to the new durable home.

The clean Resume page starts directly with the actual resume content, such as the candidate name and contact line. It does not include an internal `Job-Specific Resume` heading, because that heading was only useful as a separator when analysis and resume content shared one Notion page.

Resumes orchestrates the `Create Resume` workflow, but Notes owns Notes database validation and Note creation helpers under `src/features/notes`. The Resume Notion adapter should not become the catch-all writer for the Notes database.

The `/resumes` success message stays small but includes links to both the created Job-Specific Resume and the created Resume Fit Analysis Note. The Resume link is the application-facing output; the Note link is the audit trail for reviewing surprising generation choices.

The Notion write sequence is: create an unlinked Resume draft, write the clean Resume body, create the related Resume Fit Analysis Note linked to both the Job Posting and the Resume draft, then attach the Resume to the Job Posting as the final completion step. If anything fails before the final attach, the workflow should archive or clean up the unlinked Resume draft and any orphaned Note.

V1 does not add a `/notes` UI. Resume Fit Analysis Notes are visible through Notion relation links and the `/resumes` success message only. This keeps the change focused on moving analysis storage and preserving clean Resume pages instead of opening a notes-management workflow.

If `Create Resume` is called for a Job Posting that already has a related Resume, v1 preserves the existing idempotent behavior: return the existing Resume and do not mutate Notion. Creating or repairing missing Notes for existing Resumes belongs to a later cleanup or regeneration workflow, especially because pre-change Resumes may intentionally have Resume Fit Analysis in the Resume body.
