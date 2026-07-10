import { validateConfig } from "../../jobPostings/backend/config.js";
import { FAILURE_REASONS } from "../../jobPostings/types/contracts.js";
import {
  extractAnalyzedJobPostingSource,
  hasRelatedResume,
  isReadyForResumeCreation,
  publicResumeQueueItem,
} from "../../jobPostings/lib/resumeSource.js";
import {
  extractMasterResumeEvidenceItems,
} from "../lib/resumeBlocks.js";
import { buildResumeFitAnalysisNoteName } from "../../notes/lib/notion.js";
import { DeepSeekResumeClient } from "../lib/deepseekResume.js";
import { createResumeFitAnalysis } from "../lib/resumeFitAnalysis.js";
import { createApplicationReadyResumeDraft } from "../lib/applicationReadyResumeDraft.js";
import { createResumePdfExporter } from "../lib/pdfExport.js";
import {
  RESUME_FAILURE_REASONS,
  RESUME_RESULT_TYPES,
} from "../types/contracts.js";

export const DEFAULT_RESUME_QUEUE_LIMIT = 100;

export async function getResumeStatus({
  config,
  resumeClient,
  notesClient,
  fitRuntimeClient,
  resumeFitAnalysis = createResumeFitAnalysis({ config, fitRuntimeClient }),
}) {
  const configResult = validateResumeGenerationConfig(config);

  if (!configResult.valid) {
    return {
      ok: false,
      queueCount: 0,
      items: [],
      errors: configResult.errors,
      warnings: [],
    };
  }

  try {
    const schema = await validateResumeWorkflowSchemas({ resumeClient, notesClient });
    if (!schema.valid) {
      return {
        ok: false,
        queueCount: 0,
        items: [],
        errors: schema.errors,
        warnings: schema.warnings,
      };
    }

    const runtime = await resumeFitAnalysis.health();
    if (!runtime.ok) {
      return {
        ok: false,
        queueCount: 0,
        items: [],
        errors: ["Resume Fit Analysis runtime is unavailable. Start it with npm start."],
        warnings: schema.warnings,
      };
    }

    const items = await resumeClient.findResumeCreationQueueItems(DEFAULT_RESUME_QUEUE_LIMIT);
    return {
      ok: true,
      queueCount: items.length,
      items,
      errors: [],
      warnings: schema.warnings,
    };
  } catch (error) {
    return {
      ok: false,
      queueCount: 0,
      items: [],
      errors: [error.message || "Unable to read Resume status."],
      warnings: [],
    };
  }
}

export async function createResumeForJobPosting({
  jobPostingPageId,
  config,
  resumeClient,
  notesClient,
  fitRuntimeClient,
  resumeLlm = new DeepSeekResumeClient({
    apiKey: config.deepseekApiKey,
    model: config.deepseekModel,
  }),
  resumeFitAnalysis = createResumeFitAnalysis({
    config,
    fitRuntimeClient,
    resumeLlm,
  }),
  applicationReadyResumeDraft = createApplicationReadyResumeDraft({
    config,
    resumeGenerator: resumeLlm,
  }),
  resumePdfExporter = createResumePdfExporter(),
}) {
  const readConfigResult = validateResumeConfig(config);
  if (!readConfigResult.valid) {
    return failed(FAILURE_REASONS.INVALID_CONFIG, "Resume creation is not configured.", {
      errors: readConfigResult.errors,
    });
  }

  const pageId = String(jobPostingPageId || "").trim();
  if (!pageId) {
    return failed(FAILURE_REASONS.INVALID_REQUEST, "jobPostingPageId is required.");
  }

  const jobPostingPage = await resumeClient.getJobPostingPage(pageId);
  const existingResume = await resumeClient.findRelatedResume(jobPostingPage);

  if (existingResume) {
    return {
      type: RESUME_RESULT_TYPES.ALREADY_EXISTS,
      resume: existingResume,
      jobPosting: publicResumeQueueItem(jobPostingPage),
    };
  }

  const configResult = validateResumeGenerationConfig(config);
  if (!configResult.valid) {
    return failed(configResult.reason || FAILURE_REASONS.INVALID_CONFIG, "Resume creation is not configured.", {
      errors: configResult.errors,
    });
  }

  const runtime = await resumeFitAnalysis.health();
  if (!runtime.ok) {
    return failed(
      RESUME_FAILURE_REASONS.FIT_RUNTIME_UNAVAILABLE,
      "Resume Fit Analysis runtime is unavailable. Start it with npm start.",
    );
  }

  const schema = await validateResumeWorkflowSchemas({ resumeClient, notesClient });
  if (!schema.valid) {
    return failed(FAILURE_REASONS.INVALID_NOTION_SCHEMA, "The configured Resume workflow schema is invalid.", {
      errors: schema.errors,
      warnings: schema.warnings,
    });
  }

  if (!isReadyForResumeCreation(jobPostingPage) || hasRelatedResume(jobPostingPage)) {
    return failed(FAILURE_REASONS.INVALID_REQUEST, "Job Posting is not ready for Resume creation.");
  }

  const item = publicResumeQueueItem(jobPostingPage);
  if (!item.resumeName) {
    return failed(FAILURE_REASONS.INVALID_REQUEST, "Job Posting must have Company Name and Job Title before creating a Resume.", {
      jobPosting: item,
    });
  }

  try {
    const generation = await generateResumeContent({
      jobPostingPage,
      jobPosting: item,
      resumeName: item.resumeName,
      resumeClient,
      resumeFitAnalysis,
      applicationReadyResumeDraft,
    });

    try {
      const {
        resume,
        note,
        exportedPdf,
      } = await commitGeneratedResume({
        jobPosting: item,
        generation,
        resumeClient,
        notesClient,
        resumePdfExporter,
      });

      return {
        type: RESUME_RESULT_TYPES.CREATED,
        resume,
        note,
        exportedPdf,
        jobPosting: item,
        fitScore: generation.fitScore.overallFitScore,
      };
    } catch (error) {
      return failed(RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED, error.message || "Resume, Note, or PDF write failed.", {
        jobPosting: item,
      });
    }
  } catch (error) {
    return failed(error.reason || RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED, error.message || "Resume generation failed.", {
      jobPosting: item,
      ...(error.extra || {}),
    });
  }
}

async function generateResumeContent({
  jobPostingPage,
  jobPosting,
  resumeName,
  resumeClient,
  resumeFitAnalysis,
  applicationReadyResumeDraft,
}) {
  const jobBlocks = await resumeClient.getPageChildren(jobPostingPage.id, { recursive: true });
  const {
    jobContent,
    jobPostingAnalysis,
  } = extractAnalyzedJobPostingSource(jobBlocks);

  if (!jobContent) {
    throw resumeError(RESUME_FAILURE_REASONS.MISSING_JOB_CONTENT, "No Job Content section was found for Resume Fit Analysis.");
  }

  if (!jobPostingAnalysis) {
    throw resumeError(RESUME_FAILURE_REASONS.MISSING_JOB_POSTING_ANALYSIS, "No Job Posting Analysis section was found for Resume Fit Analysis.");
  }

  const masterPages = await resumeClient.findMasterResumePages();
  if (masterPages.length !== 1) {
    throw resumeError(RESUME_FAILURE_REASONS.MISSING_MASTER_RESUME, "Exactly one Master Resume is required for Resume generation.");
  }

  const masterBlocks = await resumeClient.getPageChildren(masterPages[0].id, { recursive: true });
  const evidenceItems = extractMasterResumeEvidenceItems(masterBlocks);
  if (evidenceItems.length === 0) {
    throw resumeError(RESUME_FAILURE_REASONS.MISSING_MASTER_RESUME, "Master Resume must contain evidence before Resume generation.");
  }

  const { fitScore } = await resumeFitAnalysis.analyze({
    jobContent,
    jobPostingAnalysis,
    masterEvidenceItems: evidenceItems,
  });

  const draft = await applicationReadyResumeDraft.create({
    resumeName,
    jobPosting,
    masterEvidenceItems: evidenceItems,
    fitScore,
  });

  return {
    resumeBlocks: draft.resumeBlocks,
    fitAnalysisBlocks: draft.fitAnalysisBlocks,
    fitScore,
  };
}

async function validateResumeWorkflowSchemas({ resumeClient, notesClient }) {
  if (!notesClient?.validateNotesWorkflowSchema) {
    return {
      valid: false,
      errors: ["Notes workflow client is required for Resume creation."],
      warnings: [],
    };
  }

  const [resumeSchema, notesSchema] = await Promise.all([
    resumeClient.validateResumeWorkflowSchema(),
    notesClient.validateNotesWorkflowSchema(),
  ]);
  const errors = [
    ...resumeSchema.errors,
    ...notesSchema.errors,
  ];

  return {
    valid: errors.length === 0,
    errors,
    warnings: [
      ...resumeSchema.warnings,
      ...notesSchema.warnings,
    ],
  };
}

async function commitGeneratedResume({
  jobPosting,
  generation,
  resumeClient,
  notesClient,
  resumePdfExporter,
}) {
  let resumeDraft = null;
  let note = null;
  let exportedPdf = null;

  try {
    resumeDraft = await resumeClient.createUnlinkedJobSpecificResume({
      resumeName: jobPosting.resumeName,
      blocks: generation.resumeBlocks,
    });

    note = await notesClient.createResumeFitAnalysisNote({
      noteName: buildResumeFitAnalysisNoteName(jobPosting),
      jobPostingPageId: jobPosting.id,
      resumePageId: resumeDraft.id,
      blocks: generation.fitAnalysisBlocks,
    });

    exportedPdf = await resumePdfExporter.save({
      jobPosting,
      resumeBlocks: generation.resumeBlocks,
    });

    const resume = await resumeClient.attachResumeToJobPosting({
      resumePageId: resumeDraft.id,
      jobPostingPageId: jobPosting.id,
    });

    return { resume, note, exportedPdf };
  } catch (error) {
    if (exportedPdf) {
      await resumePdfExporter.remove(exportedPdf).catch(() => {});
    }
    if (note) {
      await notesClient.archiveNote(note.id).catch(() => {});
    }
    if (resumeDraft) {
      await resumeClient.archiveResumePage(resumeDraft.id).catch(() => {});
    }
    throw error;
  }
}

export function validateResumeConfig(config, { requireNotes = false } = {}) {
  const base = validateConfig(config);
  const errors = [...base.errors];

  if (!config.notionResumeDatabaseId) {
    errors.push("NOTION_RESUME_DATABASE_ID is required for Resume creation.");
  }

  if (requireNotes && !config.notionNotesDatabaseId) {
    errors.push("NOTION_NOTES_DATABASE_ID is required for Resume creation.");
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export function validateResumeGenerationConfig(config) {
  const base = validateResumeConfig(config, { requireNotes: true });
  const errors = [...base.errors];
  let reason = FAILURE_REASONS.INVALID_CONFIG;

  if (!config.deepseekApiKey) {
    errors.push("DEEPSEEK_API_KEY is required for Resume generation.");
    reason = RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED;
  }

  if (!config.fitRuntimeUrl) {
    errors.push("FIT_RUNTIME_URL is required for Resume Fit Analysis.");
    reason = RESUME_FAILURE_REASONS.FIT_RUNTIME_UNAVAILABLE;
  }

  return {
    valid: errors.length === 0,
    errors,
    reason,
  };
}

function resumeError(reason, message, extra = {}) {
  const error = new Error(message);
  error.reason = reason;
  error.extra = extra;
  return error;
}

function failed(reason, message, extra = {}) {
  return {
    type: RESUME_RESULT_TYPES.FAILED,
    reason,
    message,
    ...extra,
  };
}
