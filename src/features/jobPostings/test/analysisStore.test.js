import test from "node:test";
import assert from "node:assert/strict";
import {
  ANALYSIS_STORE_LOAD_STATUSES,
  ANALYSIS_STORE_SAVE_STATUSES,
  createJobPostingAnalysisStore,
} from "../lib/analysisStore.js";
import {
  FAILURE_REASONS,
} from "../types/contracts.js";

test("Job Posting Analysis Store reports schema readiness and queue count", async () => {
  const notionClient = fakeNotionClient();
  const store = createJobPostingAnalysisStore({ notionClient });

  const readiness = await store.getReadiness();

  assert.equal(readiness.schema.valid, true);
  assert.equal(readiness.queueCount, 2);
});

test("Job Posting Analysis Store loads Job Content behind a semantic interface", async () => {
  const notionClient = fakeNotionClient({
    childrenByPage: {
      "page-1": [
        heading("heading_2", "Job Content"),
        paragraph("Build RESTful APIs with FastAPI."),
        heading("heading_2", "Company Notes"),
        paragraph("Ignore unrelated later content."),
      ],
    },
  });
  const store = createJobPostingAnalysisStore({ notionClient });

  const loaded = await store.loadAnalysisInput({ id: "page-1" });

  assert.equal(loaded.status, ANALYSIS_STORE_LOAD_STATUSES.READY);
  assert.equal(loaded.jobContent, "Build RESTful APIs with FastAPI.");
  assert.equal(loaded.blockCount, 4);
});

test("Job Posting Analysis Store repairs analyzed marker when findings already exist", async () => {
  const notionClient = fakeNotionClient({
    childrenByPage: {
      "page-1": [
        heading("heading_2", "Job Content"),
        paragraph("Use PostgreSQL."),
        heading("heading_2", "Job Posting Analysis"),
      ],
    },
  });
  const store = createJobPostingAnalysisStore({ notionClient });

  const loaded = await store.loadAnalysisInput({ id: "page-1" });

  assert.equal(loaded.status, ANALYSIS_STORE_LOAD_STATUSES.REPAIRED);
  assert.deepEqual(notionClient.marked, ["page-1"]);
});

test("Job Posting Analysis Store saves findings before marking analyzed", async () => {
  const notionClient = fakeNotionClient();
  const store = createJobPostingAnalysisStore({ notionClient });

  const saved = await store.saveAnalysisFindings({ id: "page-1" }, validAnalysis());

  assert.equal(saved.status, ANALYSIS_STORE_SAVE_STATUSES.ANALYZED);
  assert.deepEqual(notionClient.operations.map((operation) => operation.type), ["append", "mark"]);
  assert.equal(notionClient.appended[0].pageId, "page-1");
  assert.match(blockText(notionClient.appended[0].blocks[0]), /Job Posting Analysis/);
});

test("Job Posting Analysis Store reports partial failure after append succeeds", async () => {
  const notionClient = fakeNotionClient({ failMark: true });
  const store = createJobPostingAnalysisStore({ notionClient });

  const saved = await store.saveAnalysisFindings({ id: "page-1" }, validAnalysis());

  assert.equal(saved.status, ANALYSIS_STORE_SAVE_STATUSES.FAILED);
  assert.equal(saved.reason, FAILURE_REASONS.NOTION_WRITE_FAILED);
  assert.equal(saved.partial, true);
  assert.deepEqual(notionClient.operations.map((operation) => operation.type), ["append", "mark"]);
});

test("Job Posting Analysis Store reports missing Job Content as a storage outcome", async () => {
  const notionClient = fakeNotionClient({
    childrenByPage: {
      "page-1": [heading("heading_2", "Notes"), paragraph("No posting body here.")],
    },
  });
  const store = createJobPostingAnalysisStore({ notionClient });

  const loaded = await store.loadAnalysisInput({ id: "page-1" });

  assert.equal(loaded.status, ANALYSIS_STORE_LOAD_STATUSES.FAILED);
  assert.equal(loaded.reason, FAILURE_REASONS.MISSING_JOB_CONTENT);
});

function fakeNotionClient(overrides = {}) {
  return {
    queueCount: overrides.queueCount ?? 2,
    childrenByPage: overrides.childrenByPage || {},
    appended: [],
    marked: [],
    operations: [],
    async validateDatabaseSchema() {
      return overrides.schema || { valid: true, errors: [], warnings: [] };
    },
    async countAnalysisQueue() {
      return this.queueCount;
    },
    async findAnalysisQueueItems(limit) {
      return [
        { id: "page-1", title: "Engineer at Example", url: "https://notion.so/page-1" },
        { id: "page-2", title: "Developer at Example", url: "https://notion.so/page-2" },
      ].slice(0, limit);
    },
    async getPageChildren(pageId) {
      return this.childrenByPage[pageId] || [];
    },
    async appendPageChildren(pageId, blocks) {
      this.operations.push({ type: "append", pageId });
      this.appended.push({ pageId, blocks });
    },
    async markJobPostingAnalyzed(pageId) {
      this.operations.push({ type: "mark", pageId });
      if (overrides.failMark) {
        throw new Error("Notion checkbox rejected.");
      }
      this.marked.push(pageId);
    },
  };
}

function validAnalysis() {
  return {
    summary: ["One.", "Two.", "Three."],
    skillGroups: [
      {
        label: "APIs & Integrations",
        signals: [{ name: "FastAPI", evidence: "FastAPI" }],
      },
    ],
  };
}

function paragraph(content) {
  return block("paragraph", content);
}

function heading(type, content) {
  return block(type, content);
}

function block(type, content) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: [{ type: "text", plain_text: content, text: { content } }],
    },
  };
}

function blockText(block) {
  const richText = block?.[block.type]?.rich_text || [];
  return richText.map((part) => part.plain_text || part.text?.content || "").join("");
}
