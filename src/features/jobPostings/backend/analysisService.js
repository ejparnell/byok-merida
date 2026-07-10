import {
  ANALYSIS_EVENT_TYPES,
  ANALYSIS_RESULT_TYPES,
  FAILURE_REASONS,
} from "../types/contracts.js";
import {
  ANALYSIS_STORE_LOAD_STATUSES,
  ANALYSIS_STORE_SAVE_STATUSES,
  createJobPostingAnalysisStore,
} from "../lib/analysisStore.js";
import { DeepSeekAnalysisClient } from "../lib/deepseek.js";
import { validateConfig } from "./config.js";

export const DEFAULT_ANALYSIS_LIMIT = 5;
export const MIN_ANALYSIS_LIMIT = 1;
export const MAX_ANALYSIS_LIMIT = 25;

export async function getAnalysisStatus({ config, notionClient, analysisStore }) {
  const configResult = validateConfig(config);
  const warnings = [];
  let queueCount = 0;
  let schema = null;
  const store = analysisStoreFor({ analysisStore, notionClient });

  if (!config.deepseekApiKey) {
    warnings.push("DEEPSEEK_API_KEY is not configured; Job Posting Analysis is disabled.");
  }

  if (!configResult.valid) {
    return {
      ok: false,
      analysisConfigured: Boolean(config.deepseekApiKey),
      model: config.deepseekModel,
      queueCount,
      errors: configResult.errors,
      warnings,
    };
  }

  try {
    const readiness = await store.getReadiness();
    schema = readiness.schema;
    queueCount = readiness.queueCount;
    warnings.push(...(schema.warnings || []));
  } catch (error) {
    return {
      ok: false,
      analysisConfigured: Boolean(config.deepseekApiKey),
      model: config.deepseekModel,
      queueCount,
      errors: [error.message || "Unable to read analysis status."],
      warnings,
    };
  }

  return {
    ok: Boolean(schema?.valid),
    analysisConfigured: Boolean(config.deepseekApiKey),
    model: config.deepseekModel,
    queueCount,
    errors: schema?.errors || [],
    warnings,
  };
}

export async function runAnalysisBatch({
  limit,
  config,
  notionClient,
  analysisStore,
  emit = () => {},
  logger = console,
  analyzer = new DeepSeekAnalysisClient({
    apiKey: config.deepseekApiKey,
    model: config.deepseekModel,
    logger,
    debugContent: config.debugAnalysisContent,
  }),
}) {
  const normalizedLimit = normalizeAnalysisLimit(limit);
  const store = analysisStoreFor({ analysisStore, notionClient });
  const totals = {
    analyzed: 0,
    skipped: 0,
    failed: 0,
    repaired: 0,
  };

  if (!config.deepseekApiKey) {
    const message = "DEEPSEEK_API_KEY is required for Job Posting Analysis.";
    await emit(runFinishedEvent({ requested: normalizedLimit, total: 0, totals, message }));
    return { totals, results: [], message };
  }

  const schema = await store.validateSchema();
  if (!schema.valid) {
    const message = "The configured Notion database schema is invalid.";
    await emit(runFinishedEvent({ requested: normalizedLimit, total: 0, totals, message, errors: schema.errors }));
    return { totals, results: [], message, errors: schema.errors };
  }

  const queue = await store.findQueueItems(normalizedLimit);
  const results = [];

  logger.log("[job-analysis] batch start", {
    requested: normalizedLimit,
    queueCount: queue.length,
    model: config.deepseekModel,
  });

  await emit({
    type: ANALYSIS_EVENT_TYPES.RUN_STARTED,
    requested: normalizedLimit,
    total: queue.length,
    model: config.deepseekModel,
  });

  for (let index = 0; index < queue.length; index += 1) {
    const item = queue[index];
    logger.log("[job-analysis] item start", {
      index: index + 1,
      total: queue.length,
      pageId: item.id,
      title: item.title,
    });

    await emit({
      type: ANALYSIS_EVENT_TYPES.ITEM_STARTED,
      index: index + 1,
      total: queue.length,
      item,
    });

    const result = await processAnalysisItem({
      item,
      index,
      total: queue.length,
      analysisStore: store,
      analyzer,
      logger,
    });

    totals[result.status] += 1;
    results.push(result);

    await emit({
      type: ANALYSIS_EVENT_TYPES.ITEM_FINISHED,
      index: index + 1,
      total: queue.length,
      item,
      result,
    });
  }

  logger.log("[job-analysis] batch end", {
    requested: normalizedLimit,
    processed: queue.length,
    totals,
  });

  await emit(runFinishedEvent({
    requested: normalizedLimit,
    total: queue.length,
    totals,
  }));

  return { totals, results };
}

function analysisStoreFor({ analysisStore, notionClient }) {
  return analysisStore || createJobPostingAnalysisStore({ notionClient });
}

export function normalizeAnalysisLimit(limit) {
  const parsed = Number.parseInt(limit, 10);
  if (!Number.isInteger(parsed)) {
    return DEFAULT_ANALYSIS_LIMIT;
  }
  return Math.min(MAX_ANALYSIS_LIMIT, Math.max(MIN_ANALYSIS_LIMIT, parsed));
}

async function processAnalysisItem({ item, analysisStore, analyzer, logger }) {
  try {
    logger.log("[job-analysis] load analysis input", { pageId: item.id, title: item.title });
    const loaded = await analysisStore.loadAnalysisInput(item);

    if (loaded.status === ANALYSIS_STORE_LOAD_STATUSES.REPAIRED) {
      logger.warn("[job-analysis] analysis section exists; repaired checkbox", {
        pageId: item.id,
        title: item.title,
      });
      return result(ANALYSIS_RESULT_TYPES.REPAIRED, loaded.message);
    }

    if (loaded.status === ANALYSIS_STORE_LOAD_STATUSES.FAILED) {
      return failedResult(loaded.message, loaded.reason || FAILURE_REASONS.ANALYSIS_FAILED);
    }

    logger.log("[job-analysis] loaded Job Content", {
      pageId: item.id,
      title: item.title,
      blockCount: loaded.blockCount,
      jobContentLength: loaded.jobContent.length,
      jobContentPreview: preview(loaded.jobContent, 700),
    });

    logger.log("[job-analysis] DeepSeek analyze", { pageId: item.id, title: item.title });
    const analysis = await analyzer.analyzeJobContent(loaded.jobContent);

    logger.log("[job-analysis] validate analysis", {
      pageId: item.id,
      title: item.title,
      summarySentences: analysis.summary.length,
      skillGroupCount: analysis.skillGroups.length,
    });

    logger.log("[job-analysis] save analysis findings", { pageId: item.id, title: item.title });
    const saved = await analysisStore.saveAnalysisFindings(item, analysis);

    if (saved.status === ANALYSIS_STORE_SAVE_STATUSES.FAILED) {
      return failedResult(saved.message, saved.reason || FAILURE_REASONS.NOTION_WRITE_FAILED, {
        ...(saved.partial ? { partial: true } : {}),
      });
    }

    logger.log("[job-analysis] analysis findings saved", {
      pageId: item.id,
      title: item.title,
      blockCount: saved.blockCount,
    });

    return result(ANALYSIS_RESULT_TYPES.ANALYZED, saved.message);
  } catch (error) {
    logger.error("[job-analysis] item failed", {
      pageId: item.id,
      title: item.title,
      message: error.message,
    });
    return failedResult(error.message || "Job Posting Analysis failed.");
  }
}

function result(status, message, extra = {}) {
  return {
    status,
    message,
    ...extra,
  };
}

function failedResult(message, reason = FAILURE_REASONS.ANALYSIS_FAILED, extra = {}) {
  return result(ANALYSIS_RESULT_TYPES.FAILED, message, {
    reason,
    ...extra,
  });
}

function runFinishedEvent({ requested, total, totals, message, errors }) {
  return {
    type: ANALYSIS_EVENT_TYPES.RUN_FINISHED,
    requested,
    total,
    totals,
    ...(message ? { message } : {}),
    ...(errors ? { errors } : {}),
  };
}

function preview(value, maxLength) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}...` : text;
}
