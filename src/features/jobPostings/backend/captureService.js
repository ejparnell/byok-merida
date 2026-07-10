import {
  FAILURE_REASONS,
  RESULT_TYPES,
  REVIEW_CONFIDENCE_THRESHOLD,
} from "../types/contracts.js";
import {
  hasMinimumCreationFields,
  parseCaptureEvidence,
  publicParsedJobPosting,
} from "../lib/parser.js";
import { canonicalizeJobUrl } from "../lib/url.js";

export async function captureJobPosting(evidence, { notionClient, now = new Date(), debug = false }) {
  const parsed = parseCaptureEvidence(evidence);
  debugLog(debug, "parsed", {
    jobUrl: parsed.jobUrl,
    jobPostingTitle: parsed.jobPostingTitle,
    companyName: parsed.companyName,
    jobTitle: parsed.jobTitle,
    location: parsed.location,
    jobContentLength: String(parsed.jobContent || "").length,
    confidence: parsed.confidence,
    needsReview: parsed.needsReview,
    evidenceDebug: parsed.evidenceDebug,
  });

  if (!parsed.jobUrl) {
    return failed(FAILURE_REASONS.MISSING_JOB_URL, "The current page URL could not be used as a Job URL.", {
      parsed: publicParsedJobPosting(parsed),
    });
  }

  if (!parsed.jobContent) {
    return failed(FAILURE_REASONS.MISSING_JOB_CONTENT, "No readable job content was found on the current page.", {
      parsed: publicParsedJobPosting(parsed),
      debug: parsed.evidenceDebug || {},
    });
  }

  const schemaResult = await notionClient.validateDatabaseSchema();
  if (!schemaResult.valid) {
    return failed(FAILURE_REASONS.INVALID_NOTION_SCHEMA, "The configured Notion database schema is invalid.", {
      errors: schemaResult.errors,
      warnings: schemaResult.warnings,
      parsed: publicParsedJobPosting(parsed),
    });
  }

  const duplicate = await notionClient.findExistingJobPosting(parsed.jobUrl);
  if (duplicate) {
    return {
      type: RESULT_TYPES.ALREADY_CAPTURED,
      page: duplicate,
      summary: summaryFromParsed(parsed),
    };
  }

  if (!hasMinimumCreationFields(parsed) || parsed.confidence < REVIEW_CONFIDENCE_THRESHOLD) {
    return {
      type: RESULT_TYPES.NEEDS_REVIEW,
      parsed: publicParsedJobPosting(parsed),
      reasons: reviewReasons(parsed),
      summary: summaryFromParsed(parsed),
    };
  }

  const page = await notionClient.createJobPostingPage(parsed, now);
  return {
    type: RESULT_TYPES.CREATED,
    page,
    summary: summaryFromParsed(parsed),
  };
}

export function prepareJobPostingReview(evidence, { debug = false } = {}) {
  const parsed = parseCaptureEvidence(evidence);
  debugLog(debug, "parsed for review", {
    jobUrl: parsed.jobUrl,
    jobPostingTitle: parsed.jobPostingTitle,
    companyName: parsed.companyName,
    jobTitle: parsed.jobTitle,
    location: parsed.location,
    jobContentLength: String(parsed.jobContent || "").length,
    confidence: parsed.confidence,
    needsReview: parsed.needsReview,
    evidenceDebug: parsed.evidenceDebug,
  });

  return {
    type: RESULT_TYPES.PARSED,
    parsed: publicParsedJobPosting(parsed),
    reasons: reviewReasons(parsed),
    summary: summaryFromParsed(parsed),
    ...(debug ? { debug: parsed.evidenceDebug || {} } : {}),
  };
}

export async function confirmJobPosting(parsedInput, { notionClient, now = new Date(), debug = false }) {
  const parsed = normalizeConfirmedParsed(parsedInput);
  debugLog(debug, "confirmed parsed", {
    jobUrl: parsed.jobUrl,
    jobPostingTitle: parsed.jobPostingTitle,
    jobContentLength: String(parsed.jobContent || "").length,
  });

  if (!parsed.jobUrl) {
    return failed(FAILURE_REASONS.MISSING_JOB_URL, "A Job URL is required before creating the Notion page.", {
      parsed: publicParsedJobPosting(parsed),
    });
  }

  if (!parsed.jobContent) {
    return failed(FAILURE_REASONS.MISSING_JOB_CONTENT, "Job Content is required before creating the Notion page.", {
      parsed: publicParsedJobPosting(parsed),
    });
  }

  if (!hasMinimumCreationFields(parsed)) {
    return {
      type: RESULT_TYPES.NEEDS_REVIEW,
      parsed: publicParsedJobPosting(parsed),
      reasons: reviewReasons(parsed),
      summary: summaryFromParsed(parsed),
    };
  }

  const schemaResult = await notionClient.validateDatabaseSchema();
  if (!schemaResult.valid) {
    return failed(FAILURE_REASONS.INVALID_NOTION_SCHEMA, "The configured Notion database schema is invalid.", {
      errors: schemaResult.errors,
      warnings: schemaResult.warnings,
      parsed: publicParsedJobPosting(parsed),
    });
  }

  const duplicate = await notionClient.findExistingJobPosting(parsed.jobUrl);
  if (duplicate) {
    return {
      type: RESULT_TYPES.ALREADY_CAPTURED,
      page: duplicate,
      summary: summaryFromParsed(parsed),
    };
  }

  const page = await notionClient.createJobPostingPage(parsed, now);
  return {
    type: RESULT_TYPES.CREATED,
    page,
    summary: summaryFromParsed(parsed),
  };
}

export function failed(reason, message, extra = {}) {
  return {
    type: RESULT_TYPES.FAILED,
    reason,
    message,
    ...extra,
  };
}

function normalizeConfirmedParsed(input) {
  const jobUrl = canonicalizeJobUrl(input?.jobUrl);
  const capturedUrl = input?.capturedUrl && input.capturedUrl !== jobUrl ? input.capturedUrl : "";

  return {
    jobPostingTitle: String(input?.jobPostingTitle || "").trim(),
    jobUrl,
    capturedUrl,
    companyName: String(input?.companyName || "").trim(),
    jobTitle: String(input?.jobTitle || "").trim(),
    location: String(input?.location || "").trim(),
    jobContent: String(input?.jobContent || "").trim(),
    parsingNotes: Array.isArray(input?.parsingNotes) ? input.parsingNotes : [],
    needsReview: false,
    confidence: 1,
  };
}

function reviewReasons(parsed) {
  const reasons = [];
  if (!parsed.jobPostingTitle) reasons.push("Job Posting title is missing.");
  if (!parsed.jobUrl) reasons.push("Job URL is missing.");
  if (!parsed.jobContent) reasons.push("Job Content is missing.");
  if (!parsed.companyName) reasons.push("Company Name needs review.");
  if (!parsed.jobTitle) reasons.push("Job Title needs review.");
  if (!parsed.location) reasons.push("Location needs review.");
  if (parsed.confidence < REVIEW_CONFIDENCE_THRESHOLD) reasons.push("Capture confidence was low.");
  return reasons;
}

function summaryFromParsed(parsed) {
  return {
    jobPostingTitle: parsed.jobPostingTitle || "",
    companyName: parsed.companyName || "",
    jobTitle: parsed.jobTitle || "",
    location: parsed.location || "",
    jobUrl: parsed.jobUrl || "",
  };
}

function debugLog(enabled, label, payload) {
  if (enabled) {
    console.log(`[job-capture] ${label}`, payload);
  }
}
