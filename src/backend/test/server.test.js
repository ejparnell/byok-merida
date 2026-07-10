import test from "node:test";
import assert from "node:assert/strict";
import { createRouteAdapters } from "../adapters.js";
import { createServer } from "../server.js";

test("server rejects requests with an invalid capture token", async () => {
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/health`, {
      headers: { "X-Capture-Token": "wrong" },
    });
    const payload = await response.json();

    assert.equal(response.status, 401);
    assert.equal(payload.reason, "invalid_token");
  } finally {
    await close(server);
  }
});

test("server handles capture requests with a valid token", async () => {
  const notionClient = fakeNotionClient();
  const server = createTestServer({
    config: testConfig(),
    notionClient,
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/capture`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Capture-Token": "local-token",
      },
      body: JSON.stringify({
        url: "https://example.com/jobs/1",
        pageTitle: "Frontend Engineer at Example",
        selectedText: `Frontend Engineer
Company: Example
Location: Remote
Responsibilities
- Build software.
${"Useful content. ".repeat(80)}`,
      }),
    });
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.type, "created");
    assert.equal(notionClient.created.length, 1);
  } finally {
    await close(server);
  }
});

test("server handles parse requests without validating or writing to Notion", async () => {
  const notionClient = fakeNotionClient();
  const server = createTestServer({
    config: testConfig(),
    notionClient,
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/parse`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Capture-Token": "local-token",
      },
      body: JSON.stringify({
        url: "https://example.com/jobs/2?utm_source=x",
        pageTitle: "Product Engineer at Example Labs",
        selectedText: `Product Engineer
Company: Example Labs
Location: New York, NY
Responsibilities
- Build applicant tracking workflows.
${"Useful content. ".repeat(80)}`,
      }),
    });
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.type, "parsed");
    assert.equal(payload.parsed.jobUrl, "https://example.com/jobs/2");
    assert.equal(payload.parsed.companyName, "Example Labs");
    assert.equal(notionClient.schemaChecks, 0);
    assert.equal(notionClient.duplicateLookups, 0);
    assert.equal(notionClient.created.length, 0);
  } finally {
    await close(server);
  }
});

test("server serves analysis UI without a token", async () => {
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/analysis`);
    const body = await response.text();

    assert.equal(response.status, 200);
    assert.match(body, /Job Posting Analysis/);
    assert.doesNotMatch(body, /Token/);
    assert.doesNotMatch(body, /localStorage/);
  } finally {
    await close(server);
  }
});

test("server serves resume UI without a token", async () => {
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/resumes`);
    const body = await response.text();

    assert.equal(response.status, 200);
    assert.match(body, /Resume Creation/);
    assert.doesNotMatch(body, /Token/);
    assert.doesNotMatch(body, /localStorage/);
  } finally {
    await close(server);
  }
});

test("server reports analysis status with missing DeepSeek key", async () => {
  const notionClient = fakeNotionClient();
  notionClient.queueCount = 3;
  const server = createTestServer({
    config: testConfig({ deepseekApiKey: "" }),
    notionClient,
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/analysis/status`);
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.ok, true);
    assert.equal(payload.analysisConfigured, false);
    assert.equal(payload.queueCount, 3);
    assert.match(payload.warnings.join(" "), /DEEPSEEK_API_KEY/);
  } finally {
    await close(server);
  }
});

test("server reports resume status", async () => {
  const resumeClient = fakeResumeClient({
    queue: [
      {
        id: "page-1",
        url: "https://notion.so/page-1",
        companyName: "Example",
        jobTitle: "Engineer",
        resumeName: "Engineer at Example",
      },
    ],
  });
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
    resumeClient,
    fitRuntimeClient: fakeFitRuntimeClient(),
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/resumes/status`);
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.ok, true);
    assert.equal(payload.queueCount, 1);
    assert.equal(payload.items[0].resumeName, "Engineer at Example");
  } finally {
    await close(server);
  }
});

test("server streams NDJSON through the Local Operator route interface", async () => {
  const server = createTestServer({
    config: testConfig(),
    jobPostingsAdapter: {
      async validateNotionSchema() {
        return { valid: true, errors: [], warnings: [] };
      },
      routes: [
        {
          method: "GET",
          path: "/events",
          token: "none",
          async handle({ streamNdjson }) {
            await streamNdjson(async (emit) => {
              await emit({ type: "one" });
              await emit({ type: "two" });
            });
          },
        },
      ],
    },
    resumesAdapter: { routes: [] },
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/events`);
    const events = (await response.text())
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));

    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type"), /application\/x-ndjson/);
    assert.deepEqual(events, [{ type: "one" }, { type: "two" }]);
  } finally {
    await close(server);
  }
});

test("server rejects cross-origin analysis writes without a token", async () => {
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/analysis/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "https://example.com",
      },
      body: JSON.stringify({ limit: 1 }),
    });
    const payload = await response.json();

    assert.equal(response.status, 403);
    assert.equal(payload.reason, "invalid_token");
  } finally {
    await close(server);
  }
});

test("server rejects cross-origin resume writes without a token", async () => {
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
    resumeClient: fakeResumeClient(),
  });

  await listen(server);
  try {
    const response = await fetch(`${serverUrl(server)}/resumes/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "https://example.com",
      },
      body: JSON.stringify({ jobPostingPageId: "page-1" }),
    });
    const payload = await response.json();

    assert.equal(response.status, 403);
    assert.equal(payload.reason, "invalid_token");
  } finally {
    await close(server);
  }
});

test("server streams analysis run progress events", async () => {
  const notionClient = fakeNotionClient();
  notionClient.queue = [
    { id: "page-1", title: "API Engineer at Example", url: "https://notion.so/page-1" },
  ];
  notionClient.childrenByPage = {
    "page-1": [
      block("heading_2", "Job Content"),
      block("paragraph", "Build RESTful APIs with FastAPI."),
    ],
  };
  const analysisAnalyzer = {
    async analyzeJobContent() {
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
  const server = createTestServer({
    config: testConfig(),
    notionClient,
    analysisAnalyzer,
  });

  await listen(server);
  try {
    const origin = serverUrl(server);
    const response = await fetch(`${origin}/analysis/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: origin,
      },
      body: JSON.stringify({ limit: 1 }),
    });
    const events = (await response.text())
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));

    assert.equal(response.status, 200);
    assert.equal(events[0].type, "run_started");
    assert.equal(events[1].type, "item_started");
    assert.equal(events[2].type, "item_finished");
    assert.equal(events[2].result.status, "analyzed");
    assert.equal(events[3].type, "run_finished");
    assert.equal(notionClient.appended.length, 1);
    assert.deepEqual(notionClient.marked, ["page-1"]);
  } finally {
    await close(server);
  }
});

test("server creates a resume from same-origin resume UI", async () => {
  const resumeClient = fakeResumeClient({
    createdResult: {
      type: "created",
      resume: {
        id: "resume-page",
        url: "https://notion.so/resume-page",
        name: "Engineer at Example",
      },
    },
  });
  const server = createTestServer({
    config: testConfig(),
    notionClient: fakeNotionClient(),
    resumeClient,
    fitRuntimeClient: fakeFitRuntimeClient(),
    resumeLlm: fakeResumeLlm(),
  });

  await listen(server);
  try {
    const origin = serverUrl(server);
    const response = await fetch(`${origin}/resumes/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: origin,
      },
      body: JSON.stringify({ jobPostingPageId: "page-1" }),
    });
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.type, "created");
    assert.equal(payload.resume.url, "https://notion.so/resume-page");
    assert.equal(payload.note.url, "https://notion.so/note-page");
    assert.equal(payload.exportedPdf.relativePath, "export/Example-ElizabethParnell.pdf");
  } finally {
    await close(server);
  }
});

function createTestServer({
  config = testConfig(),
  adapters,
  jobPostingsAdapter,
  resumesAdapter,
  notionClient = fakeNotionClient(),
  resumeClient,
  notesClient = fakeNotesClient(),
  analysisAnalyzer,
  resumeFitAnalysis,
  fitRuntimeClient,
  resumeLlm,
  resumePdfExporter = fakeResumePdfExporter(),
} = {}) {
  return createServer({
    config,
    adapters: adapters || createRouteAdapters({
      config,
      jobPostings: {
        ...(jobPostingsAdapter ? { adapter: jobPostingsAdapter } : {}),
        ...(notionClient ? { notionClient } : {}),
        ...(analysisAnalyzer ? { analysisAnalyzer } : {}),
      },
      resumes: {
        ...(resumesAdapter ? { adapter: resumesAdapter } : {}),
        ...(resumeClient ? { resumeClient } : {}),
        ...(notesClient ? { notesClient } : {}),
        ...(resumeFitAnalysis ? { resumeFitAnalysis } : {}),
        ...(fitRuntimeClient ? { fitRuntimeClient } : {}),
        ...(resumeLlm ? { resumeLlm } : {}),
        resumePdfExporter,
      },
    }),
  });
}

function testConfig(overrides = {}) {
  return {
    notionToken: "secret",
    notionDatabaseId: "database",
    notionResumeDatabaseId: "resume-database",
    notionNotesDatabaseId: "notes-database",
    captureToken: "local-token",
    extensionOrigin: "chrome-extension://abc",
    port: 3217,
    fitRuntimeUrl: "http://127.0.0.1:3218",
    fitRuntimePort: 3218,
    deepseekApiKey: "deepseek-secret",
    deepseekModel: "deepseek-v4-flash",
    ...overrides,
  };
}

function fakeResumeClient(overrides = {}) {
  return {
    queue: overrides.queue || [],
    created: [],
    attached: [],
    archived: [],
    async validateResumeWorkflowSchema() {
      return { valid: true, errors: [], warnings: [] };
    },
    async findResumeCreationQueueItems() {
      return this.queue;
    },
    async getJobPostingPage() {
      return {
        id: "page-1",
        properties: {
          "Company Name": {
            rich_text: [{ plain_text: "Example" }],
          },
          "Job Title": {
            rich_text: [{ plain_text: "Engineer" }],
          },
          "Application Status": {
            select: { name: "To Apply" },
          },
          Analyzed: {
            checkbox: true,
          },
          Resumes: {
            relation: [],
          },
        },
      };
    },
    async findRelatedResume() {
      return null;
    },
    async getPageChildren(pageId) {
      if (pageId === "master-page") {
        return templateMasterChildren();
      }
      return [
        block("heading_2", "Job Content"),
        block("paragraph", "Build REST APIs with PostgreSQL."),
        block("heading_2", "Job Posting Analysis"),
        block("paragraph", "The role needs REST APIs and PostgreSQL."),
      ];
    },
    async findMasterResumePages() {
      return [{ id: "master-page", url: "https://notion.so/master", name: "Master Resume" }];
    },
    async createUnlinkedJobSpecificResume(input) {
      this.created.push(input);
      return overrides.createdResult?.resume || {
        id: "resume-page",
        url: "https://notion.so/resume-page",
        name: input.resumeName,
      };
    },
    async attachResumeToJobPosting(input) {
      this.attached.push(input);
      return overrides.createdResult?.resume || {
        id: input.resumePageId,
        url: "https://notion.so/resume-page",
        name: "Engineer at Example",
      };
    },
    async archiveResumePage(pageId) {
      this.archived.push(pageId);
    },
  };
}

function fakeNotesClient(overrides = {}) {
  return {
    created: [],
    archived: [],
    async validateNotesWorkflowSchema() {
      return overrides.schema || { valid: true, errors: [], warnings: [] };
    },
    async createResumeFitAnalysisNote(input) {
      this.created.push(input);
      return overrides.createdNote || {
        id: "note-page",
        url: "https://notion.so/note-page",
        name: input.noteName,
      };
    },
    async archiveNote(noteId) {
      this.archived.push(noteId);
    },
  };
}

function fakeResumePdfExporter(overrides = {}) {
  return {
    saved: [],
    removed: [],
    async save(input) {
      this.saved.push(input);
      if (overrides.saveFails) {
        throw new Error("PDF write failed.");
      }
      return overrides.exportedPdf || {
        path: "/tmp/export/Example-ElizabethParnell.pdf",
        relativePath: "export/Example-ElizabethParnell.pdf",
        fileName: "Example-ElizabethParnell.pdf",
      };
    },
    async remove(exportedPdf) {
      this.removed.push(exportedPdf);
    },
  };
}

function fakeFitRuntimeClient() {
  return {
    async health() {
      return { ok: true };
    },
    async candidates() {
      return {
        ok: true,
        candidates: [
          {
            requirementId: "req-1",
            matches: [
              {
                evidenceId: "evidence-3",
                keywordCoverage: 0.9,
                tfidfSimilarity: 0.8,
                normalizedSkillOverlap: ["REST APIs"],
                sectionHint: false,
                score: 0.9,
              },
            ],
          },
        ],
      };
    },
    async score() {
      return {
        ok: true,
        generationAllowed: true,
        overallFitScore: 0.9,
        categoryScores: [{ category: "APIs & Integrations", fitScore: 0.9, requirementCount: 1 }],
        requirements: [
          {
            requirementId: "req-1",
            text: "Build REST APIs",
            type: "required skill",
            category: "APIs & Integrations",
            importance: "required",
            evidenceStrength: "direct evidence",
            matches: [
              {
                evidenceId: "evidence-3",
                evidenceStrength: "direct evidence",
                evidenceText: "Built REST APIs backed by PostgreSQL.",
                sourceSection: "Software Engineer, ClinMatchGO",
              },
            ],
          },
        ],
        gaps: [],
      };
    },
  };
}

function fakeResumeLlm() {
  return {
    async extractFitRequirements() {
      return [
        {
          id: "req-1",
          text: "Build REST APIs",
          type: "required skill",
          category: "APIs & Integrations",
          importance: "required",
          evidence: "REST APIs",
        },
      ];
    },
    async generateResume() {
      return {
        name: "Elizabeth Parnell",
        summary: "Engineer focused on REST APIs.",
        skills: [],
        roles: [
          {
            templateId: "clinmatchgo-software-engineer",
            sourceSection: "Software Engineer, ClinMatchGO",
            heading: "Software Engineer, ClinMatchGO",
            title: "Software Engineer",
            organization: "ClinMatchGO",
            dateRange: "2025 - Present",
            bullets: ["Built REST APIs backed by PostgreSQL."],
            claimTraces: [
              {
                bulletIndex: 0,
                evidenceIds: ["evidence-3"],
                requirementIds: ["req-1"],
              },
            ],
          },
        ],
        sections: [],
      };
    },
  };
}

function fakeNotionClient() {
  return {
    created: [],
    appended: [],
    marked: [],
    queue: [],
    queueCount: 0,
    childrenByPage: {},
    schemaChecks: 0,
    duplicateLookups: 0,
    async validateDatabaseSchema() {
      this.schemaChecks += 1;
      return { valid: true, errors: [], warnings: [] };
    },
    async findExistingJobPosting() {
      this.duplicateLookups += 1;
      return null;
    },
    async createJobPostingPage(parsed) {
      this.created.push(parsed);
      return { id: "created-page", url: "https://notion.so/created-page" };
    },
    async countAnalysisQueue() {
      return this.queueCount;
    },
    async findAnalysisQueueItems(limit) {
      return this.queue.slice(0, limit);
    },
    async getPageChildren(pageId) {
      return this.childrenByPage[pageId] || [];
    },
    async appendPageChildren(pageId, blocks) {
      this.appended.push({ pageId, blocks });
    },
    async markJobPostingAnalyzed(pageId) {
      this.marked.push(pageId);
    },
  };
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

function templateMasterChildren() {
  return [
    block("heading_2", "Work Experience"),
    block("heading_3", "Software Engineer, ClinMatchGO"),
    ...numberedBullets("Built REST APIs backed by PostgreSQL", 5),
    block("heading_3", "AI Studio Coach, Break Through Tech"),
    ...numberedBullets("Coached student teams building applied ML apps", 5),
    block("heading_3", "Lead Instructor, General Assembly"),
    ...numberedBullets("Taught JavaScript React and MongoDB architecture", 5),
    block("heading_3", "Software Engineer, Wayfair"),
    ...numberedBullets("Supported gift card transaction reliability", 5),
  ];
}

function numberedBullets(prefix, count) {
  return Array.from({ length: count }, (_, index) => block("bulleted_list_item", `${prefix} ${index + 1}.`));
}

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
}

function close(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
}

function serverUrl(server) {
  const address = server.address();
  return `http://${address.address}:${address.port}`;
}
