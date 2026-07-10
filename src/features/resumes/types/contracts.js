export const RESUME_PROPERTIES = {
  NAME: "Name",
  JOB_POSTING: "Job Posting",
};

export { JOB_POSTING_RESUME_RELATION } from "../../jobPostings/types/contracts.js";

export const RESUME_RESULT_TYPES = {
  CREATED: "created",
  ALREADY_EXISTS: "already_exists",
  FAILED: "failed",
};

export const RESUME_FAILURE_REASONS = {
  FIT_RUNTIME_UNAVAILABLE: "fit_runtime_unavailable",
  MISSING_MASTER_RESUME: "missing_master_resume",
  MISSING_JOB_CONTENT: "missing_job_content",
  MISSING_JOB_POSTING_ANALYSIS: "missing_job_posting_analysis",
  INSUFFICIENT_MASTER_RESUME_EVIDENCE: "insufficient_master_resume_evidence",
  RESUME_GENERATION_FAILED: "resume_generation_failed",
};
