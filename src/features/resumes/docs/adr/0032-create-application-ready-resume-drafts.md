# Create application-ready Resume drafts

`Create Resume` must end with an application-ready Job-Specific Resume, not just a Resume Fit Analysis. The workflow is only complete when the Resume page contains a tailored summary, skills, and work-experience roles from the Master Resume.

For work experience, generation uses the full Master Resume role skeleton. Every Master Resume work-experience role must appear in the Job-Specific Resume, even when that role is not the strongest match for the Job Posting. Each work-experience role must have 5 to 7 evidence-backed bullets, with 6 preferred. Job-supported evidence is used first for tailoring emphasis, then the server fills from the role's remaining Master Resume bullet evidence so the final draft is complete.

If the LLM returns a thin draft or omits a role, the server fills the missing role/bullets from Master Resume evidence before writing to Notion. If a Master Resume work-experience role has fewer than 5 source bullet evidence items, generation fails before creating the related Resume rather than writing a resume that is too thin to apply with.

This keeps the created Resume usable for applying to a job.

The earlier combined-page layout is superseded by ADR-0035. Resume Fit Analysis now belongs in a related Note, and the Resume page starts directly with the real resume content instead of an internal `Job-Specific Resume` separator heading.
