import {
  normalizeAnalysisLimit,
  runAnalysisBatch,
} from "../../../src/features/jobPostings/backend/analysisService.js";
import { NotionClient } from "../../../src/features/jobPostings/lib/notion.js";
import {
  ANALYSIS_STORE_LOAD_STATUSES,
  ANALYSIS_STORE_SAVE_STATUSES,
  createJobPostingAnalysisStore,
} from "../../../src/features/jobPostings/lib/analysisStore.js";
import { parseAndValidateAnalysisJson } from "../../../src/features/jobPostings/lib/analysisBlocks.js";
import {
  createCallCounter,
  prototypeConfig,
  quietLogger,
} from "./observerSupport.js";

export async function observeAnalysisFixture(fixture) {
  switch (fixture.observation.runner) {
    case "analysis_failure_isolation":
      return observeFailureIsolation(fixture);
    case "analysis_repair":
      return observeRepair(fixture);
    case "analysis_validation_persistence_matrix":
      return observeValidationPersistenceMatrix(fixture);
    case "analysis_queue_contract":
      return observeQueueContract(fixture);
    default:
      throw new Error(`Unsupported Application Analysis runner: ${fixture.observation.runner}`);
  }
}

async function observeQueueContract(fixture) {
  const calls = createCallCounter();
  let queryBody = null;
  const notionClient = new NotionClient({
    token: "notion-secret",
    databaseId: "applications-database",
    fetchImpl: async (_url, options) => {
      calls.increment("queryAnalysisQueue");
      queryBody = JSON.parse(options.body);
      return {
        ok: true,
        async json() {
          return {
            results: fixture.observation.dependencyOutputs.notionResults.map((item) => (
              queuePage(item.id, item.title)
            )),
            has_more: false,
            next_cursor: null,
          };
        },
      };
    },
  });
  const requestedLimit = fixture.observation.initialState.requestedLimit;
  const items = await notionClient.findAnalysisQueueItems(requestedLimit);

  return {
    outcome: {
      itemCount: items.length,
      requestedLimit,
      prototypeClampedMaximum: normalizeAnalysisLimit(99),
    },
    effects: [],
    state: {
      queryFilter: queryBody.filter,
      pageSize: queryBody.page_size,
      itemIds: items.map((item) => item.id),
    },
    callCounts: calls.snapshot(["queryAnalysisQueue"]),
    cleanupResidue: {},
  };
}

async function observeValidationPersistenceMatrix(fixture) {
  const effects = [];
  const calls = createCallCounter();
  const state = { analysisBodyHeadings: [], analyzed: false };
  const { jobContent, validModelOutput, unsupportedModelOutput } = fixture.observation.initialState;
  calls.increment("validateAnalysisOutput");
  const valid = parseAndValidateAnalysisJson(JSON.stringify(validModelOutput), jobContent);
  let unsupportedRejected = false;
  try {
    calls.increment("validateAnalysisOutput");
    parseAndValidateAnalysisJson(JSON.stringify(unsupportedModelOutput), jobContent);
  } catch {
    unsupportedRejected = true;
  }
  const notionClient = {
    async appendPageChildren(_applicationId, blocks) {
      calls.increment("appendPageChildren");
      effects.push("append_analysis_body");
      state.analysisBodyHeadings = blocks
        .filter((block) => block.type.startsWith("heading_"))
        .map((block) => block[block.type].rich_text[0].text.content)
        .filter((heading) => ["Job Posting Analysis", "Summary", "Skill Signals"].includes(heading));
    },
    async markJobPostingAnalyzed() {
      calls.increment("markJobPostingAnalyzed");
      effects.push("commit_analyzed_property");
      throw new Error("Property update failed.");
    },
  };
  const store = createJobPostingAnalysisStore({ notionClient });
  const saved = await store.saveAnalysisFindings(
    { id: "application-partial", title: "Platform Engineer at Example" },
    valid,
  );
  const signalNames = valid.skillGroups.flatMap((group) => group.signals.map((signal) => signal.name));

  return {
    outcome: {
      summarySentenceCount: valid.summary.length,
      signalNames,
      unsupportedRejected,
      persistenceStatus: saved.status,
      partial: Boolean(saved.partial),
    },
    effects,
    state,
    callCounts: calls.snapshot([
      "validateAnalysisOutput",
      "appendPageChildren",
      "markJobPostingAnalyzed",
    ]),
    cleanupResidue: {
      analysisBodyPresent: state.analysisBodyHeadings.includes("Job Posting Analysis"),
      analyzed: state.analyzed,
    },
  };
}

async function observeFailureIsolation(fixture) {
  const effects = [];
  const calls = createCallCounter();
  const initialState = fixture.observation.initialState;
  const analyzerOutputs = fixture.observation.dependencyOutputs.analyzerByApplication;
  const applicationByContent = new Map(
    Object.entries(initialState.jobContentByApplication).map(([id, content]) => [content, id]),
  );
  const queue = initialState.queue.map((id) => ({
    id,
    title: id === "application-bad" ? "Bad Application" : "Good Application",
    url: `https://notion.so/${id}`,
  }));
  const state = { analysisBodies: [], analyzedMarkers: [] };
  const analysisStore = {
    async validateSchema() {
      calls.increment("validateSchema");
      return { valid: true, errors: [], warnings: [] };
    },
    async findQueueItems(limit) {
      calls.increment("findQueueItems");
      return queue.slice(0, limit);
    },
    async loadAnalysisInput(item) {
      calls.increment("loadAnalysisInput");
      effects.push(`load:${item.id}`);
      return {
        status: ANALYSIS_STORE_LOAD_STATUSES.READY,
        jobContent: initialState.jobContentByApplication[item.id],
        blockCount: 2,
      };
    },
    async saveAnalysisFindings(item) {
      calls.increment("saveAnalysisFindings");
      effects.push(`save:${item.id}`);
      state.analysisBodies.push(item.id);
      state.analyzedMarkers.push(item.id);
      return {
        status: ANALYSIS_STORE_SAVE_STATUSES.ANALYZED,
        message: "Analysis appended and Analyzed checkbox checked.",
        blockCount: 4,
      };
    },
  };
  const analyzer = {
    async analyzeJobContent(jobContent) {
      calls.increment("analyzeJobContent");
      const applicationId = applicationByContent.get(jobContent);
      effects.push(`analyze:${applicationId}`);
      const output = analyzerOutputs[applicationId];
      if (output.error) throw new Error(output.error);
      return output;
    },
  };
  const result = await runAnalysisBatch({
    limit: queue.length,
    config: prototypeConfig(),
    analysisStore,
    analyzer,
    logger: quietLogger(),
  });

  return {
    outcome: {
      failed: result.totals.failed,
      analyzed: result.totals.analyzed,
      repaired: result.totals.repaired,
    },
    effects,
    state,
    callCounts: calls.snapshot([
      "validateSchema",
      "findQueueItems",
      "loadAnalysisInput",
      "analyzeJobContent",
      "saveAnalysisFindings",
    ]),
    cleanupResidue: { savedApplications: [...state.analysisBodies] },
  };
}

async function observeRepair(fixture) {
  const effects = [];
  const calls = createCallCounter();
  const applicationId = fixture.observation.initialState.queue[0];
  const state = { analysisBodies: [applicationId], analyzedMarkers: [] };
  const analysisStore = {
    async validateSchema() {
      calls.increment("validateSchema");
      return { valid: true, errors: [], warnings: [] };
    },
    async findQueueItems() {
      calls.increment("findQueueItems");
      return [{ id: applicationId, title: "Repair Application" }];
    },
    async loadAnalysisInput(item) {
      calls.increment("loadAnalysisInput");
      effects.push(`load:${item.id}`);
      state.analyzedMarkers.push(item.id);
      return {
        status: ANALYSIS_STORE_LOAD_STATUSES.REPAIRED,
        message: "Existing analysis section found; Analyzed checkbox repaired.",
      };
    },
    async saveAnalysisFindings(item) {
      calls.increment("saveAnalysisFindings");
      effects.push(`save:${item.id}`);
      return { status: ANALYSIS_STORE_SAVE_STATUSES.ANALYZED };
    },
  };
  const analyzer = {
    async analyzeJobContent() {
      calls.increment("analyzeJobContent");
      effects.push(`analyze:${applicationId}`);
      throw new Error("Analyzer must not be called for repair.");
    },
  };
  const result = await runAnalysisBatch({
    limit: 1,
    config: prototypeConfig(),
    analysisStore,
    analyzer,
    logger: quietLogger(),
  });

  return {
    outcome: {
      failed: result.totals.failed,
      analyzed: result.totals.analyzed,
      repaired: result.totals.repaired,
    },
    effects,
    state,
    callCounts: calls.snapshot([
      "validateSchema",
      "findQueueItems",
      "loadAnalysisInput",
      "analyzeJobContent",
      "saveAnalysisFindings",
    ]),
    cleanupResidue: { savedApplications: [] },
  };
}

function queuePage(id, title) {
  return {
    id,
    url: `https://notion.so/${id}`,
    properties: {
      "Job Posting": {
        title: [{ type: "text", plain_text: title, text: { content: title } }],
      },
    },
  };
}
