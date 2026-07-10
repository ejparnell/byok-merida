import {
  FAILURE_REASONS,
} from "../types/contracts.js";
import {
  buildAnalysisBlocks,
  extractJobContentFromBlocks,
  hasAnalysisSection,
} from "./analysisBlocks.js";

export const ANALYSIS_STORE_LOAD_STATUSES = {
  READY: "ready",
  REPAIRED: "repaired",
  FAILED: "failed",
};

export const ANALYSIS_STORE_SAVE_STATUSES = {
  ANALYZED: "analyzed",
  FAILED: "failed",
};

export function createJobPostingAnalysisStore({ notionClient }) {
  return new JobPostingAnalysisStore({ notionClient });
}

class JobPostingAnalysisStore {
  constructor({ notionClient }) {
    this.notionClient = notionClient;
  }

  async getReadiness() {
    const schema = await this.notionClient.validateDatabaseSchema();
    const queueCount = schema.valid ? await this.notionClient.countAnalysisQueue() : 0;

    return {
      schema,
      queueCount,
    };
  }

  async validateSchema() {
    return this.notionClient.validateDatabaseSchema();
  }

  async findQueueItems(limit) {
    return this.notionClient.findAnalysisQueueItems(limit);
  }

  async loadAnalysisInput(item) {
    const children = await this.notionClient.getPageChildren(item.id);

    if (hasAnalysisSection(children)) {
      return this.repairAnalyzedMarker(item);
    }

    const jobContent = extractJobContentFromBlocks(children);
    if (!jobContent) {
      return {
        status: ANALYSIS_STORE_LOAD_STATUSES.FAILED,
        message: "No Job Content section was found for analysis.",
        reason: FAILURE_REASONS.MISSING_JOB_CONTENT,
        blockCount: children.length,
      };
    }

    return {
      status: ANALYSIS_STORE_LOAD_STATUSES.READY,
      jobContent,
      blockCount: children.length,
    };
  }

  async saveAnalysisFindings(item, analysis) {
    const blocks = buildAnalysisBlocks(analysis);

    try {
      await this.notionClient.appendPageChildren(item.id, blocks);
    } catch (error) {
      return {
        status: ANALYSIS_STORE_SAVE_STATUSES.FAILED,
        message: error.message || "Unable to append Job Posting Analysis findings.",
        reason: FAILURE_REASONS.NOTION_WRITE_FAILED,
        blockCount: blocks.length,
      };
    }

    try {
      await this.notionClient.markJobPostingAnalyzed(item.id);
    } catch (error) {
      return {
        status: ANALYSIS_STORE_SAVE_STATUSES.FAILED,
        message: `Analysis appended, but Analyzed checkbox update failed: ${error.message}`,
        reason: FAILURE_REASONS.NOTION_WRITE_FAILED,
        partial: true,
        blockCount: blocks.length,
      };
    }

    return {
      status: ANALYSIS_STORE_SAVE_STATUSES.ANALYZED,
      message: "Analysis appended and Analyzed checkbox checked.",
      blockCount: blocks.length,
    };
  }

  async repairAnalyzedMarker(item) {
    try {
      await this.notionClient.markJobPostingAnalyzed(item.id);
      return {
        status: ANALYSIS_STORE_LOAD_STATUSES.REPAIRED,
        message: "Existing analysis section found; Analyzed checkbox repaired.",
      };
    } catch (error) {
      return {
        status: ANALYSIS_STORE_LOAD_STATUSES.FAILED,
        message: `Existing analysis section found, but checkbox repair failed: ${error.message}`,
        reason: FAILURE_REASONS.NOTION_WRITE_FAILED,
      };
    }
  }
}
