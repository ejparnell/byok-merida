export const RESULT_TYPES = {
  PARSED: "parsed",
  CREATED: "created",
  ALREADY_CAPTURED: "already_captured",
  NEEDS_REVIEW: "needs_review",
  FAILED: "failed",
};

export const FAILURE_REASONS = {
  BACKEND_OFFLINE: "backend_offline",
  INVALID_TOKEN: "invalid_token",
  INVALID_CONFIG: "invalid_config",
  INVALID_NOTION_SCHEMA: "invalid_notion_schema",
  DUPLICATE_LOOKUP_FAILED: "duplicate_lookup_failed",
  MISSING_JOB_CONTENT: "missing_job_content",
  MISSING_JOB_URL: "missing_job_url",
  NOTION_WRITE_FAILED: "notion_write_failed",
  INVALID_REQUEST: "invalid_request",
  ANALYSIS_NOT_CONFIGURED: "analysis_not_configured",
  ANALYSIS_FAILED: "analysis_failed",
};

export const NOTION_PROPERTIES = {
  JOB_POSTING: "Job Posting",
  COMPANY_NAME: "Company Name",
  JOB_TITLE: "Job Title",
  JOB_URL: "Job URL",
  CAPTURED_URL: "Captured URL",
  LOCATION: "Location",
  APPLICATION_STATUS: "Application Status",
  MATCH_SCORE: "Match Score",
  APPLICATION_DATE: "Application Date",
  ANALYZED: "Analyzed",
};

export const JOB_POSTING_RESUME_RELATION = "Resumes";

export const APPLICATION_STATUS_TO_APPLY = "To Apply";

export const REVIEW_CONFIDENCE_THRESHOLD = 0.65;

export const ANALYSIS_RESULT_TYPES = {
  ANALYZED: "analyzed",
  SKIPPED: "skipped",
  FAILED: "failed",
  REPAIRED: "repaired",
};

export const ANALYSIS_EVENT_TYPES = {
  RUN_STARTED: "run_started",
  ITEM_STARTED: "item_started",
  ITEM_FINISHED: "item_finished",
  RUN_FINISHED: "run_finished",
};
