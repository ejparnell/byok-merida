# Block resume creation when fit analysis runtime is unavailable

The `/resumes` page does not fall back to blank Resume creation when the Resume Fit Analysis runtime is unavailable. Because `Create Resume` now means evidence-grounded analysis plus resume generation, `/resumes/status` should report a blocked state and disable `Create Resume` until the local Python service is available through `npm start`; otherwise a blank related Resume would remove the Job Posting from the queue without producing the promised output.
