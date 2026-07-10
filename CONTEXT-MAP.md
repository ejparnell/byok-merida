# Context Map

## Contexts

- [Job Postings](./src/features/jobPostings/CONTEXT.md) - owns captured job posting language, including the posting record created from a job description webpage.
- [Resumes](./src/features/resumes/CONTEXT.md) - owns resume records used as the source material and generated output for applications.
- [Notes](./src/features/notes/CONTEXT.md) - owns analysis and supporting notes related to Job Postings and Resumes.

## Relationships

- **Resumes -> Job Postings**: Resumes references Job Postings when a resume is created for a specific analyzed opportunity; Job Postings exposes the inverse Notion relation as `Resumes`.
- **Notes -> Job Postings**: Notes references Job Postings when a note explains, analyzes, or supports a specific captured opportunity; Job Postings exposes the inverse Notion relation as `Notes`.
- **Notes -> Resumes**: Notes references Resumes when a note explains, analyzes, or supports a specific Resume; Resumes exposes the inverse Notion relation as `Notes`.
