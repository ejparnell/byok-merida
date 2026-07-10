# Notes

Notes owns the language for supporting Notion notes that are related to Job Postings, Resumes, or both.

## Language

**Note**:
A Notion record that stores supporting analysis or context related to a Job Posting, a Resume, or both. A Note is not the employer-facing Resume and is not the captured Job Posting itself.
_Avoid_: Resume, Job Posting, hidden metadata

**Note Name**:
The title of a Note. A Resume Fit Analysis Note uses `Resume Fit Analysis - {Job Title} at {Company Name}` so it is distinguishable from the related Job-Specific Resume.
_Avoid_: Resume Name, note title

**Configured Notes Database**:
The existing Notion database selected as the destination for Notes. Resume creation requires this database to have `Name`, `Job Posting`, and `Resume` properties with inverse `Notes` relations on the Job Posting and Resume databases.
_Avoid_: Generated notes database, optional resume storage

**Resume Fit Analysis Note**:
A Note that stores the Resume Fit Analysis for one Job Posting and one Job-Specific Resume. It is related to both records so the Resume can stay limited to employer-facing resume content while the analysis remains durable and auditable.
_Avoid_: Resume body analysis, job analysis, scratch note

**Orphaned Resume Fit Analysis Note**:
A Resume Fit Analysis Note created during a failed `Create Resume` workflow before the related Resume was completed and attached to the Job Posting. In v1, an orphaned note is cleanup state and is not reused as source material for a retry.
_Avoid_: Reusable analysis, completed note
