# Resumes

Resumes owns the language for resume records in the user's Notion workspace, including the master source resume and job-specific resumes created from analyzed Job Postings.

## Language

**Resume**:
A Notion record representing a resume document or resume placeholder. A Resume may be the master source record or a job-specific record associated with a Job Posting.
_Avoid_: Document, CV

**Resume Name**:
The title of a Resume. The Master Resume uses the fixed name `Master Resume`, while a Job-Specific Resume uses the related Job Posting title format: `{Job Title} at {Company Name}`.
_Avoid_: Resume title, version name

**Master Resume**:
The canonical source Resume named `Master Resume` that future job-specific resumes are based on. The Master Resume is not itself created for a specific Job Posting.
_Avoid_: Base resume, source document

**Master Resume Evidence Item**:
A meaningful unit extracted from the Master Resume for Resume Fit Analysis, such as a role heading, role summary, bullet, project entry, skill or tool list, education or certification line, or outcome statement. Each item keeps its source section and original text.
_Avoid_: Resume chunk, source blob

**Job-Specific Resume**:
A Resume created for one Job Posting from the Master Resume and the related Job Posting's analysis. A Job-Specific Resume contains only the application-ready resume content with a tailored summary, skills, and work-experience roles; supporting analysis belongs in a related Note.
_Avoid_: Generated resume, tailored resume

**Application-Ready Resume Draft**:
The employer-facing content inside a Job-Specific Resume that the user can apply with after review. Every Master Resume work-experience role is preserved and must have 5 to 7 evidence-backed bullets, with 6 preferred. If a Master Resume role has fewer than 5 source bullet evidence items, creation fails before writing the Job-Specific Resume.
_Avoid_: Analysis-only output, short resume sketch

**Resume PDF Export**:
A local PDF file saved when `Create Resume` completes a Job-Specific Resume. The file lives in the repo root `export` folder and uses the name `{CompanyName}-ElizabethParnell.pdf`.
_Avoid_: Notion file attachment, application submission

**Resume Fit Analysis**:
A comparison between the Master Resume and one Job Posting that maps job requirements to resume evidence before a Job-Specific Resume is written. It uses Job Content as the source of truth, uses Job Posting Analysis as supporting structure, includes explicit ML/NLP analysis such as keyword coverage and semantic similarity, and is stored in a related Note instead of the Resume page body.
_Avoid_: Match score, job analysis, resume draft

**Fit Requirement**:
A concrete demand or signal extracted from Job Content for Resume Fit Analysis, such as a responsibility, required skill, preferred skill, tool or technology, seniority signal, domain signal, work-style signal, or qualification. Vague traits are not Fit Requirements unless the Job Content ties them to concrete work.
_Avoid_: Generic trait, standalone soft skill

**Skill Normalization**:
The Resume Fit Analysis practice of mapping near-duplicate skill, tool, and technology terms to canonical names before comparison.
_Avoid_: Taxonomy integration, scattered aliases

**Evidence Strength**:
The Resume Fit Analysis classification for how well Master Resume evidence supports a Fit Requirement. Supported values are `direct evidence`, `adjacent evidence`, `weak evidence`, and `no evidence`; only direct or adjacent evidence can support new job-specific emphasis for a Fit Requirement.
_Avoid_: Confidence label, match label

**Fit Score**:
A Resume Fit Analysis score calculated per Fit Requirement and summarized by category. Fit Score guides resume emphasis but is not the Job Posting `Match Score`.
_Avoid_: Match Score, objective score

**Resume Claim Trace**:
The evidence mapping from a Job-Specific Resume claim back to one or more Master Resume evidence items and, when applicable, the Fit Requirements it supports. Resume Claim Traces are used internally during validation and persisted as human-readable evidence details in the Resume Fit Analysis.
_Avoid_: Citation, footnote, hidden note

**Resume Attachment**:
The Notion relation connecting a Job-Specific Resume to its Job Posting. In the first version, the attachment itself is the durable proof that a resume exists for the Job Posting.
_Avoid_: Resume status, has-resume flag

**Resume Creation Queue**:
The set of Analyzed Job Postings that are still `To Apply` and do not already have a related Job-Specific Resume. This queue represents opportunities ready for first resume creation, not every analyzed posting.
_Avoid_: All analyzed jobs, resume backlog
