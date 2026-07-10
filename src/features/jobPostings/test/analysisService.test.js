import test from "node:test";
import assert from "node:assert/strict";
import {
  getAnalysisStatus,
  normalizeAnalysisLimit,
  runAnalysisBatch,
} from "../backend/analysisService.js";
import {
  ANALYSIS_STORE_LOAD_STATUSES,
  ANALYSIS_STORE_SAVE_STATUSES,
} from "../lib/analysisStore.js";

test("normalizeAnalysisLimit defaults and clamps batch size", () => {
  assert.equal(normalizeAnalysisLimit(undefined), 5);
  assert.equal(normalizeAnalysisLimit(0), 1);
  assert.equal(normalizeAnalysisLimit(99), 25);
  assert.equal(normalizeAnalysisLimit(7), 7);
});

test("getAnalysisStatus reports missing DeepSeek without breaking queue count", async () => {
  const status = await getAnalysisStatus({
    config: testConfig({ deepseekApiKey: "" }),
    analysisStore: fakeAnalysisStore(),
  });

  assert.equal(status.ok, true);
  assert.equal(status.analysisConfigured, false);
  assert.equal(status.queueCount, 2);
  assert.match(status.warnings.join(" "), /DEEPSEEK_API_KEY/);
});

test("runAnalysisBatch repairs existing analysis without appending duplicate blocks", async () => {
  const analysisStore = fakeAnalysisStore({
    queue: [{ id: "page-1", title: "Engineer at Example", url: "https://notion.so/page-1" }],
    loadedByPage: {
      "page-1": {
        status: ANALYSIS_STORE_LOAD_STATUSES.REPAIRED,
        message: "Existing analysis section found; Analyzed checkbox repaired.",
      },
    },
  });
  const analyzer = {
    async analyzeJobContent() {
      throw new Error("Analyzer should not be called.");
    },
  };

  const events = [];
  const result = await runAnalysisBatch({
    limit: 1,
    config: testConfig(),
    analysisStore,
    analyzer,
    emit: async (event) => events.push(event),
    logger: quietLogger(),
  });

  assert.equal(result.totals.repaired, 1);
  assert.deepEqual(analysisStore.loaded, ["page-1"]);
  assert.deepEqual(analysisStore.saved, []);
  assert.equal(events.at(-1).type, "run_finished");
});

test("runAnalysisBatch continues after a per-posting analysis failure", async () => {
  const analysisStore = fakeAnalysisStore({
    queue: [
      { id: "page-1", title: "Bad Posting", url: "https://notion.so/page-1" },
      { id: "page-2", title: "Good Posting", url: "https://notion.so/page-2" },
    ],
    loadedByPage: {
      "page-1": {
        status: ANALYSIS_STORE_LOAD_STATUSES.READY,
        jobContent: "Use PostgreSQL.",
        blockCount: 2,
      },
      "page-2": {
        status: ANALYSIS_STORE_LOAD_STATUSES.READY,
        jobContent: "Build RESTful APIs with FastAPI.",
        blockCount: 2,
      },
    },
  });
  const analyzer = {
    async analyzeJobContent(jobContent) {
      if (jobContent.includes("PostgreSQL")) {
        throw new Error("Malformed model output.");
      }

      return {
        summary: ["One.", "Two.", "Three."],
        skillGroups: [
          {
            label: "APIs & Integrations",
            signals: [{ name: "FastAPI", evidence: "FastAPI" }],
          },
        ],
      };
    },
  };

  const result = await runAnalysisBatch({
    limit: 2,
    config: testConfig(),
    analysisStore,
    analyzer,
    logger: quietLogger(),
  });

  assert.equal(result.totals.failed, 1);
  assert.equal(result.totals.analyzed, 1);
  assert.deepEqual(analysisStore.saved, ["page-2"]);
});

function testConfig(overrides = {}) {
  return {
    notionToken: "secret",
    notionDatabaseId: "database",
    captureToken: "local-token",
    extensionOrigin: "chrome-extension://abc",
    port: 3217,
    deepseekApiKey: "deepseek-secret",
    deepseekModel: "deepseek-v4-flash",
    ...overrides,
  };
}

function fakeAnalysisStore(overrides = {}) {
  const store = {
    queue: overrides.queue || [
      { id: "page-1", title: "Engineer at Example", url: "https://notion.so/page-1" },
      { id: "page-2", title: "Developer at Example", url: "https://notion.so/page-2" },
    ],
    loadedByPage: overrides.loadedByPage || {},
    loaded: [],
    saved: [],
    async getReadiness() {
      const schema = await this.validateSchema();
      return {
        schema,
        queueCount: schema.valid ? this.queue.length : 0,
      };
    },
    async validateSchema() {
      return { valid: true, errors: [], warnings: [] };
    },
    async findQueueItems(limit) {
      return this.queue.slice(0, limit);
    },
    async loadAnalysisInput(item) {
      this.loaded.push(item.id);
      return this.loadedByPage[item.id] || {
        status: ANALYSIS_STORE_LOAD_STATUSES.READY,
        jobContent: "Build RESTful APIs with FastAPI.",
        blockCount: 2,
      };
    },
    async saveAnalysisFindings(item) {
      this.saved.push(item.id);
      return {
        status: ANALYSIS_STORE_SAVE_STATUSES.ANALYZED,
        message: "Analysis appended and Analyzed checkbox checked.",
        blockCount: 4,
      };
    },
  };

  return store;
}

function quietLogger() {
  return {
    log() {},
    warn() {},
    error() {},
  };
}
