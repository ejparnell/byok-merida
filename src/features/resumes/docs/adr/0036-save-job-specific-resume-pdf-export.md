# Save Job-Specific Resume PDF export locally

`Create Resume` saves a local PDF copy of the clean Job-Specific Resume when it creates the Notion Resume page.

The PDF is generated from the same employer-facing Resume blocks written to the Resume page. It does not include Resume Fit Analysis blocks, because those belong in the related Note. This keeps the local file aligned with the document the user may inspect and apply with.

PDF exports live in the repo root `export` folder and are named `{CompanyName}-ElizabethParnell.pdf`, for example `ExampleHealth-ElizabethParnell.pdf`. The folder is gitignored because these files are local generated artifacts, not source-controlled project state.

The PDF write is part of the `Create Resume` completion sequence. The workflow creates the unlinked Resume draft, creates the related Resume Fit Analysis Note, writes the PDF export, and only then attaches the Resume to the Job Posting. If PDF export fails, the workflow archives the unlinked Resume draft and the orphaned Note instead of marking the Job Posting complete.

If the final Resume attachment fails after the PDF has been written, the workflow removes the local PDF export during cleanup and archives the unlinked Notion artifacts. This preserves the existing rule that the Job Posting Resume relation is the durable completion signal.

V1 does not upload the PDF to Notion or add a separate PDF-management UI. The `/resumes` success message reports the local export path alongside the Resume and Analysis Note links.
