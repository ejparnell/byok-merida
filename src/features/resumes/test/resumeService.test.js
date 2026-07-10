import test from "node:test";
import assert from "node:assert/strict";
import {
  createResumeForJobPosting,
  getResumeStatus,
  validateResumeConfig,
  validateResumeGenerationConfig,
} from "../backend/resumeService.js";
import {
  APPLICATION_STATUS_TO_APPLY,
  FAILURE_REASONS,
  NOTION_PROPERTIES,
} from "../../jobPostings/types/contracts.js";
import {
  JOB_POSTING_RESUME_RELATION,
  RESUME_FAILURE_REASONS,
  RESUME_PROPERTIES,
  RESUME_RESULT_TYPES,
} from "../types/contracts.js";

test("validateResumeConfig requires only the resume database in addition to base config", () => {
  const result = validateResumeConfig(testConfig({ notionResumeDatabaseId: "" }));

  assert.equal(result.valid, false);
  assert.match(result.errors.join(" "), /NOTION_RESUME_DATABASE_ID/);
});

test("validateResumeGenerationConfig does not require a paid embedding provider", () => {
  const result = validateResumeGenerationConfig(testConfig());

  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("validateResumeGenerationConfig requires the Notes database for Resume creation", () => {
  const result = validateResumeGenerationConfig(testConfig({ notionNotesDatabaseId: "" }));

  assert.equal(result.valid, false);
  assert.match(result.errors.join(" "), /NOTION_NOTES_DATABASE_ID/);
});

test("getResumeStatus returns ready queue items", async () => {
  const resumeClient = fakeResumeClient({
    queue: [{ id: "page-1", resumeName: "Engineer at Example" }],
  });
  const notesClient = fakeNotesClient();

  const status = await getResumeStatus({
    config: testConfig(),
    resumeClient,
    notesClient,
    resumeFitAnalysis: fakeResumeFitAnalysis(),
  });

  assert.equal(status.ok, true);
  assert.equal(status.queueCount, 1);
  assert.equal(status.items[0].resumeName, "Engineer at Example");
});

test("getResumeStatus reports missing resume database config without querying Notion", async () => {
  const resumeClient = fakeResumeClient();

  const status = await getResumeStatus({
    config: testConfig({ notionResumeDatabaseId: "" }),
    resumeClient,
  });

  assert.equal(status.ok, false);
  assert.equal(resumeClient.schemaChecks, 0);
  assert.match(status.errors.join(" "), /NOTION_RESUME_DATABASE_ID/);
});

test("getResumeStatus blocks invalid schema", async () => {
  const status = await getResumeStatus({
    config: testConfig(),
    resumeClient: fakeResumeClient({
      schema: { valid: false, errors: ["Bad relation."], warnings: [] },
    }),
    notesClient: fakeNotesClient(),
    resumeFitAnalysis: fakeResumeFitAnalysis(),
  });

  assert.equal(status.ok, false);
  assert.equal(status.queueCount, 0);
  assert.match(status.errors.join(" "), /Bad relation/);
});

test("getResumeStatus supports an empty queue", async () => {
  const status = await getResumeStatus({
    config: testConfig(),
    resumeClient: fakeResumeClient({ queue: [] }),
    notesClient: fakeNotesClient(),
    resumeFitAnalysis: fakeResumeFitAnalysis(),
  });

  assert.equal(status.ok, true);
  assert.equal(status.queueCount, 0);
  assert.deepEqual(status.items, []);
});

test("getResumeStatus blocks when the fit runtime is unavailable", async () => {
  const status = await getResumeStatus({
    config: testConfig(),
    resumeClient: fakeResumeClient(),
    notesClient: fakeNotesClient(),
    resumeFitAnalysis: fakeResumeFitAnalysis({ health: { ok: false } }),
  });

  assert.equal(status.ok, false);
  assert.match(status.errors.join(" "), /runtime is unavailable/);
});

test("createResumeForJobPosting commits generated body through the Resume Notion adapter", async () => {
  const events = [];
  const resumeClient = fakeResumeClient({
    jobPostingPage: jobPostingPage(),
    events,
  });
  const notesClient = fakeNotesClient({ events });
  const resumePdfExporter = fakeResumePdfExporter({ events });

  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient,
    resumePdfExporter,
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.CREATED);
  assert.equal(result.resume.name, "Engineer at Example");
  assert.equal(result.note.name, "Resume Fit Analysis - Engineer at Example");
  assert.equal(result.exportedPdf.relativePath, "export/Example-ElizabethParnell.pdf");
  assert.deepEqual(events, ["create-unlinked-resume", "create-note", "save-pdf", "attach-resume"]);
  assert.deepEqual(resumeClient.childrenCalls, [
    { pageId: "job-page", recursive: true },
    { pageId: "master-page", recursive: true },
  ]);
  assert.equal(resumeClient.created[0].resumeName, "Engineer at Example");
  assert.equal(resumeClient.created[0].blocks[0].heading_1.rich_text[0].text.content, "Elizabeth Parnell");
  assert.equal(notesClient.created[0].noteName, "Resume Fit Analysis - Engineer at Example");
  assert.equal(notesClient.created[0].jobPostingPageId, "job-page");
  assert.equal(notesClient.created[0].resumePageId, "resume-page");
  assert.equal(notesClient.created[0].blocks[0].heading_2.rich_text[0].text.content, "Resume Fit Analysis");
  assert.equal(resumePdfExporter.saved[0].jobPosting.companyName, "Example");
  assert.equal(resumePdfExporter.saved[0].resumeBlocks[0].heading_1.rich_text[0].text.content, "Elizabeth Parnell");
  assert.equal(hasBlockText(resumeClient.created[0].blocks, "heading_1", "Elizabeth Parnell"), true);
  assert.equal(hasBlockText(resumeClient.created[0].blocks, "heading_2", "Resume Fit Analysis"), false);
});

test("createResumeForJobPosting returns an existing related Resume", async () => {
  const resumeClient = fakeResumeClient({
    jobPostingPage: jobPostingPage({ resumes: [{ id: "resume-page" }] }),
    existingResume: {
      id: "resume-page",
      url: "https://notion.so/resume-page",
      name: "Engineer at Example",
    },
  });
  const notesClient = fakeNotesClient();
  const resumePdfExporter = fakeResumePdfExporter();

  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient,
    resumePdfExporter,
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.ALREADY_EXISTS);
  assert.equal(result.resume.id, "resume-page");
  assert.equal(resumeClient.created.length, 0);
  assert.equal(notesClient.schemaChecks, 0);
  assert.equal(notesClient.created.length, 0);
  assert.equal(resumePdfExporter.saved.length, 0);
});

test("createResumeForJobPosting rejects a not-ready Job Posting", async () => {
  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient: fakeResumeClient({
      jobPostingPage: jobPostingPage({ status: "Applied" }),
    }),
    notesClient: fakeNotesClient(),
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.equal(result.reason, FAILURE_REASONS.INVALID_REQUEST);
  assert.match(result.message, /not ready/);
});

test("createResumeForJobPosting rejects missing Company Name or Job Title", async () => {
  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient: fakeResumeClient({
      jobPostingPage: jobPostingPage({ companyName: "" }),
    }),
    notesClient: fakeNotesClient(),
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.equal(result.reason, FAILURE_REASONS.INVALID_REQUEST);
  assert.match(result.message, /Company Name and Job Title/);
});

test("createResumeForJobPosting does not create a draft when evidence is insufficient", async () => {
  const resumeClient = fakeResumeClient();
  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient: fakeNotesClient(),
    resumeFitAnalysis: fakeResumeFitAnalysis({
      fitScore: {
        ok: true,
        generationAllowed: false,
        overallFitScore: 0.1,
        categoryScores: [],
        requirements: [
          {
            requirementId: "req-1",
            text: "Build REST APIs",
            type: "required skill",
            importance: "required",
            evidenceStrength: "no evidence",
            matches: [],
          },
        ],
        gaps: [
          {
            requirementId: "req-1",
            text: "Build REST APIs",
            evidenceStrength: "no evidence",
          },
        ],
      },
    }),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.equal(result.reason, RESUME_FAILURE_REASONS.INSUFFICIENT_MASTER_RESUME_EVIDENCE);
  assert.equal(result.fitSummary.evidenceItemCount, 25);
  assert.equal(result.fitSummary.supportedRequiredRequirementCount, 0);
  assert.equal(result.fitSummary.requiredRequirementCount, 1);
  assert.equal(resumeClient.created.length, 0);
});

test("createResumeForJobPosting reports Resume Notion adapter write failures", async () => {
  const events = [];
  const resumeClient = fakeResumeClient({ createFails: true });
  const notesClient = fakeNotesClient({ events });
  resumeClient.events = events;
  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient,
    resumePdfExporter: fakeResumePdfExporter(),
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.equal(result.reason, RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED);
  assert.match(result.message, /Append failed/);
  assert.deepEqual(events, ["create-unlinked-resume"]);
  assert.equal(notesClient.created.length, 0);
});

test("createResumeForJobPosting archives the unlinked Resume when Note creation fails", async () => {
  const events = [];
  const resumeClient = fakeResumeClient({ events });
  const notesClient = fakeNotesClient({ events, createFails: true });
  const resumePdfExporter = fakeResumePdfExporter({ events });

  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient,
    resumePdfExporter,
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.match(result.message, /Note append failed/);
  assert.deepEqual(events, ["create-unlinked-resume", "create-note", "archive-resume"]);
  assert.deepEqual(resumeClient.archived, ["resume-page"]);
  assert.equal(resumeClient.attached.length, 0);
  assert.equal(resumePdfExporter.saved.length, 0);
});

test("createResumeForJobPosting archives the Note and draft Resume when PDF export fails", async () => {
  const events = [];
  const resumeClient = fakeResumeClient({ events });
  const notesClient = fakeNotesClient({ events });
  const resumePdfExporter = fakeResumePdfExporter({ events, saveFails: true });

  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient,
    resumePdfExporter,
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.match(result.message, /PDF write failed/);
  assert.deepEqual(events, ["create-unlinked-resume", "create-note", "save-pdf", "archive-note", "archive-resume"]);
  assert.deepEqual(notesClient.archived, ["note-page"]);
  assert.deepEqual(resumeClient.archived, ["resume-page"]);
  assert.equal(resumeClient.attached.length, 0);
});

test("createResumeForJobPosting archives the Note and draft Resume when final attach fails", async () => {
  const events = [];
  const resumeClient = fakeResumeClient({ events, attachFails: true });
  const notesClient = fakeNotesClient({ events });
  const resumePdfExporter = fakeResumePdfExporter({ events });

  const result = await createResumeForJobPosting({
    jobPostingPageId: "job-page",
    config: testConfig(),
    resumeClient,
    notesClient,
    resumePdfExporter,
    resumeFitAnalysis: fakeResumeFitAnalysis(),
    resumeLlm: fakeResumeLlm(),
  });

  assert.equal(result.type, RESUME_RESULT_TYPES.FAILED);
  assert.match(result.message, /Attach failed/);
  assert.deepEqual(events, ["create-unlinked-resume", "create-note", "save-pdf", "attach-resume", "remove-pdf", "archive-note", "archive-resume"]);
  assert.deepEqual(resumePdfExporter.removed.map((pdf) => pdf.relativePath), ["export/Example-ElizabethParnell.pdf"]);
  assert.deepEqual(notesClient.archived, ["note-page"]);
  assert.deepEqual(resumeClient.archived, ["resume-page"]);
});

function testConfig(overrides = {}) {
  return {
    notionToken: "secret",
    notionDatabaseId: "job-db",
    notionResumeDatabaseId: "resume-db",
    notionNotesDatabaseId: "notes-db",
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
  const events = overrides.events || [];
  return {
    schemaChecks: 0,
    created: [],
    attached: [],
    archived: [],
    childrenCalls: [],
    events,
    schema: overrides.schema || { valid: true, errors: [], warnings: [] },
    queue: overrides.queue || [],
    jobPostingPage: overrides.jobPostingPage || jobPostingPage(),
    existingResume: overrides.existingResume || null,
    jobChildren: overrides.jobChildren || [
      block("heading_2", "Job Content"),
      block("paragraph", "Build REST APIs with PostgreSQL."),
      block("heading_2", "Job Posting Analysis"),
      block("paragraph", "The role needs REST APIs and PostgreSQL."),
    ],
    masterPages: overrides.masterPages || [
      { id: "master-page", url: "https://notion.so/master", name: "Master Resume" },
    ],
    masterChildren: overrides.masterChildren || templateMasterChildren(),
    createFails: overrides.createFails || false,
    attachFails: overrides.attachFails || false,
    async validateResumeWorkflowSchema() {
      this.schemaChecks += 1;
      return this.schema;
    },
    async findResumeCreationQueueItems() {
      return this.queue;
    },
    async getJobPostingPage() {
      return this.jobPostingPage;
    },
    async findRelatedResume() {
      return this.existingResume;
    },
    async getPageChildren(pageId, options = {}) {
      this.childrenCalls.push({ pageId, recursive: Boolean(options.recursive) });
      return pageId === "master-page" ? this.masterChildren : this.jobChildren;
    },
    async findMasterResumePages() {
      return this.masterPages;
    },
    async createUnlinkedJobSpecificResume(input) {
      this.events.push("create-unlinked-resume");
      this.created.push(input);
      if (this.createFails) {
        throw new Error("Append failed.");
      }
      return {
        id: "resume-page",
        url: "https://notion.so/resume-page",
        name: input.resumeName,
      };
    },
    async attachResumeToJobPosting(input) {
      this.events.push("attach-resume");
      this.attached.push(input);
      if (this.attachFails) {
        throw new Error("Attach failed.");
      }
      return {
        id: input.resumePageId,
        url: "https://notion.so/resume-page",
        name: "Engineer at Example",
      };
    },
    async archiveResumePage(pageId) {
      this.events.push("archive-resume");
      this.archived.push(pageId);
    },
  };
}

function fakeNotesClient(overrides = {}) {
  const events = overrides.events || [];
  return {
    schemaChecks: 0,
    created: [],
    archived: [],
    schema: overrides.schema || { valid: true, errors: [], warnings: [] },
    async validateNotesWorkflowSchema() {
      this.schemaChecks += 1;
      return this.schema;
    },
    async createResumeFitAnalysisNote(input) {
      this.created.push(input);
      events.push("create-note");
      if (overrides.createFails) {
        throw new Error("Note append failed.");
      }
      return {
        id: "note-page",
        url: "https://notion.so/note-page",
        name: input.noteName,
      };
    },
    async archiveNote(noteId) {
      events.push("archive-note");
      this.archived.push(noteId);
    },
  };
}

function fakeResumePdfExporter(overrides = {}) {
  const events = overrides.events || [];
  return {
    saved: [],
    removed: [],
    async save(input) {
      this.saved.push(input);
      events.push("save-pdf");
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
      events.push("remove-pdf");
      this.removed.push(exportedPdf);
    },
  };
}

function fakeResumeFitAnalysis(overrides = {}) {
  const fitScore = overrides.fitScore || {
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

  return {
    async health() {
      return overrides.health || { ok: true };
    },
    async analyze({ masterEvidenceItems = [] } = {}) {
      if (overrides.error) {
        throw overrides.error;
      }

      if (fitScore.generationAllowed === false) {
        const error = new Error("Insufficient Master Resume evidence to create a truthful Job-Specific Resume.");
        error.reason = RESUME_FAILURE_REASONS.INSUFFICIENT_MASTER_RESUME_EVIDENCE;
        error.extra = {
          fitSummary: overrides.fitSummary || {
            evidenceItemCount: masterEvidenceItems.length,
            supportedRequiredRequirementCount: 0,
            requiredRequirementCount: 1,
            supportedRequirementCount: 0,
            scoredRequirementCount: (fitScore.requirements || []).length,
          },
        };
        throw error;
      }

      return { fitScore };
    },
  };
}

function fakeResumeLlm(overrides = {}) {
  return {
    async generateResume() {
      return overrides.generatedResume || {
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

function templateMasterChildren({ bulletCount = 5 } = {}) {
  return [
    block("heading_2", "Work Experience"),
    block("heading_3", "Software Engineer, ClinMatchGO"),
    ...numberedBullets("Built REST APIs backed by PostgreSQL", bulletCount),
    block("heading_3", "AI Studio Coach, Break Through Tech"),
    ...numberedBullets("Coached student teams building applied ML apps", bulletCount),
    block("heading_3", "Lead Instructor, General Assembly"),
    ...numberedBullets("Taught JavaScript React and MongoDB architecture", bulletCount),
    block("heading_3", "Software Engineer, Wayfair"),
    ...numberedBullets("Supported gift card transaction reliability", bulletCount),
  ];
}

function numberedBullets(prefix, count) {
  return Array.from({ length: count }, (_, index) => block("bulleted_list_item", `${prefix} ${index + 1}.`));
}

function hasBlockText(blocks, type, expectedText) {
  return blocks.some((blockItem) => blockItem.type === type && blockText(blockItem) === expectedText);
}

function blockText(blockItem) {
  const typed = blockItem?.[blockItem.type];
  return (typed?.rich_text || [])
    .map((part) => part.plain_text || part.text?.content || "")
    .join("")
    .trim();
}

function jobPostingPage({
  companyName = "Example",
  jobTitle = "Engineer",
  status = APPLICATION_STATUS_TO_APPLY,
  analyzed = true,
  resumes = [],
} = {}) {
  return {
    id: "job-page",
    url: "https://notion.so/job-page",
    properties: {
      [NOTION_PROPERTIES.COMPANY_NAME]: richText(companyName),
      [NOTION_PROPERTIES.JOB_TITLE]: richText(jobTitle),
      [NOTION_PROPERTIES.APPLICATION_STATUS]: {
        select: { name: status },
      },
      [NOTION_PROPERTIES.ANALYZED]: {
        checkbox: analyzed,
      },
      [JOB_POSTING_RESUME_RELATION]: {
        type: "relation",
        relation: resumes,
      },
      [RESUME_PROPERTIES.NAME]: {
        title: [],
      },
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

function richText(content) {
  return {
    rich_text: content ? [{ type: "text", plain_text: content, text: { content } }] : [],
  };
}
