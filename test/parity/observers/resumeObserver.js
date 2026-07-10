import { createResumeForJobPosting } from "../../../src/features/resumes/backend/resumeService.js";
import { ApplicationReadyResumeDraft } from "../../../src/features/resumes/lib/applicationReadyResumeDraft.js";
import { extractMasterResumeEvidenceItems } from "../../../src/features/resumes/lib/resumeBlocks.js";
import { RESUME_FAILURE_REASONS } from "../../../src/features/resumes/types/contracts.js";
import {
  blockText,
  createCallCounter,
  notionBlock,
  resumeConfig,
  richText,
} from "./observerSupport.js";

const CALL_NAMES = [
  "findRelatedResume",
  "fitAnalysis",
  "resumeModel",
  "createResume",
  "createNote",
  "savePdf",
  "attachResume",
  "removePdf",
  "archiveNote",
  "archiveResume",
];

export async function observeResumeFixture(fixture) {
  switch (fixture.observation.runner) {
    case "resume_evidence_blocked":
      return observeEvidenceBlocked(fixture);
    case "resume_existing":
      return observeExisting(fixture);
    case "resume_success":
      return observeSuccess(fixture);
    case "resume_final_attach_failure":
      return observeFinalAttachFailure(fixture);
    case "resume_cleanup_matrix":
      return observeCleanupMatrix(fixture);
    case "resume_source_validation_matrix":
      return observeSourceValidationMatrix(fixture);
    case "resume_claim_guardrails":
      return observeClaimGuardrails(fixture);
    default:
      throw new Error(`Unsupported Resume Creation runner: ${fixture.observation.runner}`);
  }
}

async function observeClaimGuardrails(fixture) {
  const calls = createCallCounter();
  const input = fixture.observation.initialState;
  const dependencies = fixture.observation.dependencyOutputs;
  const inventedClaim = input.generatedClaim;
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: {
      async generateResume() {
        calls.increment("resumeModel");
        return {
          name: "Elizabeth Parnell",
          summary: "Engineer focused on reliable REST APIs.",
          skills: [],
          roles: [{
            templateId: input.generatedTemplateId,
            sourceSection: input.generatedRole,
            heading: input.generatedRole,
            title: "Software Engineer",
            organization: "Wayfair",
            dateRange: "2018 - 2021",
            bullets: [inventedClaim],
            claimTraces: [{
              bulletIndex: 0,
              evidenceIds: [input.citedEvidenceId],
              requirementIds: [dependencies.fitRequirementId],
            }],
          }],
          sections: [],
        };
      },
    },
  });
  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: {
      id: "application-1",
      companyName: "Example",
      jobTitle: "Engineer",
      resumeName: "Engineer at Example",
    },
    masterEvidenceItems: extractMasterResumeEvidenceItems(prototypeMasterResumeBlocks()),
    fitScore: supportedFitScore({
      requirementId: dependencies.fitRequirementId,
      evidenceId: dependencies.supportedEvidenceId,
      evidenceOwner: input.evidenceOwner,
    }),
  });
  const renderedText = result.resumeBlocks.map(blockText);
  const renderedHeadings = headings(result.resumeBlocks);

  return {
    outcome: {
      unsupportedClaimPresent: renderedText.includes(inventedClaim),
      crossRoleClaimPresent: renderedText.some((text) => (
        text.includes("Built REST APIs backed by PostgreSQL")
        && renderedText.indexOf(text) > renderedText.indexOf("Wayfair | 2018 - 2021")
      )),
      roleCount: roleBulletCounts(result.resumeBlocks).length,
      allRolesAtLeastFiveBullets: roleBulletCounts(result.resumeBlocks).every((count) => count >= 5),
    },
    effects: [],
    state: {
      workExperienceHeadings: renderedHeadings.filter((heading) => (
        heading !== "Elizabeth Parnell" && heading !== "Summary"
      )),
      roleBulletCounts: roleBulletCounts(result.resumeBlocks),
    },
    callCounts: calls.snapshot(["resumeModel"]),
    cleanupResidue: {},
  };
}

async function observeSourceValidationMatrix(fixture) {
  const cases = [
    ["missingJobContent", { applicationBlocks: analysisOnlyBlocks() }],
    ["missingAnalysis", { applicationBlocks: jobContentOnlyBlocks() }],
    ["noMasterResume", { masterPages: [] }],
    ["multipleMasterResumes", {
      masterPages: [
        { id: "master-resume", name: "Master Resume" },
        { id: "master-resume-2", name: "Master Resume" },
      ],
    }],
    ["emptyMasterEvidence", { masterBlocks: [] }],
    ["tooFewRoleBullets", { masterBlocks: prototypeMasterResumeBlocks(4) }],
  ];
  const results = {};

  for (const [caseName, options] of cases) {
    const scenario = createResumeScenario(options);
    const result = await runResume(fixture, scenario, {
      resumeFitAnalysis: supportedFitAnalysis(scenario.calls),
      resumeLlm: supportedResumeModel(scenario.calls),
    });
    const state = normalizedResumeState(scenario);
    results[caseName] = {
      outcome: { type: result.type, reason: result.reason },
      effects: [...scenario.effects],
      state: {
        activeResumes: state.resumes.filter((resume) => !resume.archived).length,
        activeNotes: state.notes.filter((note) => !note.archived).length,
        pdfs: state.pdfs.length,
        resumeRelation: state.resumeRelation,
      },
      calls: scenario.calls.snapshot(["fitAnalysis", "resumeModel", "createResume", "createNote", "savePdf"]),
    };
  }

  return {
    outcome: Object.fromEntries(cases.map(([name]) => [name, results[name].outcome])),
    effects: cases.flatMap(([name]) => results[name].effects.map((effect) => `${name}:${effect}`)),
    state: Object.fromEntries(cases.map(([name]) => [name, results[name].state])),
    callCounts: Object.fromEntries(cases.map(([name]) => [name, results[name].calls])),
    cleanupResidue: Object.fromEntries(cases.map(([name]) => [name, results[name].state])),
  };
}

async function observeCleanupMatrix(fixture) {
  const stages = [
    ["noteFailure", { noteFails: true }],
    ["pdfFailure", { pdfFails: true }],
    ["attachFailure", { attachFails: true }],
  ];
  const observations = {};

  for (const [stage, options] of stages) {
    const scenario = createResumeScenario(options);
    const result = await runResume(fixture, scenario, {
      resumeFitAnalysis: supportedFitAnalysis(scenario.calls),
      resumeLlm: supportedResumeModel(scenario.calls),
    });
    observations[stage] = observeScenarioResult(result, scenario);
  }

  return {
    outcome: Object.fromEntries(
      stages.map(([stage]) => [stage, observations[stage].outcome]),
    ),
    effects: stages.flatMap(([stage]) => (
      observations[stage].effects.map((effect) => `${stage}:${effect}`)
    )),
    state: Object.fromEntries(stages.map(([stage]) => [stage, observations[stage].state])),
    callCounts: Object.fromEntries(
      stages.map(([stage]) => [stage, observations[stage].callCounts]),
    ),
    cleanupResidue: Object.fromEntries(
      stages.map(([stage]) => [stage, observations[stage].cleanupResidue]),
    ),
  };
}

async function observeEvidenceBlocked(fixture) {
  const scenario = createResumeScenario();
  const result = await runResume(fixture, scenario, {
    resumeFitAnalysis: blockedFitAnalysis(scenario.calls),
    resumeLlm: forbiddenResumeModel(scenario.calls),
  });
  return observeScenarioResult(result, scenario);
}

async function observeExisting(fixture) {
  const existingResumeId = fixture.observation.initialState.existingResumeId;
  const scenario = createResumeScenario({ existingResumeId });
  const result = await runResume(fixture, scenario, {
    resumeFitAnalysis: forbiddenFitAnalysis(scenario.calls),
    resumeLlm: forbiddenResumeModel(scenario.calls),
  });
  return observeScenarioResult(result, scenario);
}

async function observeSuccess(fixture) {
  const scenario = createResumeScenario();
  const result = await runResume(fixture, scenario, {
    resumeFitAnalysis: supportedFitAnalysis(scenario.calls),
    resumeLlm: supportedResumeModel(scenario.calls),
  });
  return observeScenarioResult(result, scenario);
}

async function observeFinalAttachFailure(fixture) {
  const scenario = createResumeScenario({ attachFails: true });
  const result = await runResume(fixture, scenario, {
    resumeFitAnalysis: supportedFitAnalysis(scenario.calls),
    resumeLlm: supportedResumeModel(scenario.calls),
  });
  return observeScenarioResult(result, scenario);
}

async function runResume(fixture, scenario, { resumeFitAnalysis, resumeLlm }) {
  return createResumeForJobPosting({
    jobPostingPageId: fixture.observation.initialState.applicationId,
    config: resumeConfig(),
    resumeClient: scenario.resumeClient,
    notesClient: scenario.notesClient,
    resumePdfExporter: scenario.pdfExporter,
    resumeFitAnalysis,
    resumeLlm,
  });
}

function observeScenarioResult(result, scenario) {
  const state = normalizedResumeState(scenario);
  const outcome = result.type === "created"
    ? {
        type: result.type,
        resumeId: result.resume?.id || null,
        noteId: result.note?.id || null,
        pdfCreated: Boolean(result.exportedPdf),
      }
    : result.type === "already_exists"
      ? { type: result.type, resumeId: result.resume?.id || null }
      : { type: result.type, reason: result.reason };

  return {
    outcome,
    effects: [...scenario.effects],
    state,
    callCounts: scenario.calls.snapshot(CALL_NAMES),
    cleanupResidue: {
      createdResumes: state.resumes.filter((resume) => (
        !resume.archived && !scenario.initialResumeIds.has(resume.id)
      )).length,
      createdNotes: state.notes.filter((note) => !note.archived).length,
      savedPdfs: state.pdfs.length,
      archivedResumes: state.resumes.filter((resume) => resume.archived).length,
      archivedNotes: state.notes.filter((note) => note.archived).length,
      removedPdfs: scenario.state.removedPdfs.length,
      resumeRelation: [...state.resumeRelation],
    },
  };
}

function createResumeScenario({
  attachFails = false,
  noteFails = false,
  pdfFails = false,
  existingResumeId = null,
  applicationBlocks = prototypeApplicationBlocks(),
  masterPages = [{ id: "master-resume", name: "Master Resume" }],
  masterBlocks = prototypeMasterResumeBlocks(),
} = {}) {
  const effects = [];
  const calls = createCallCounter();
  const state = {
    resumes: existingResumeId
      ? [{ id: existingResumeId, blocks: [], archived: false }]
      : [],
    notes: [],
    pdfs: [],
    removedPdfs: [],
    resumeRelation: existingResumeId ? [existingResumeId] : [],
  };
  const resumeClient = {
    state,
    async getJobPostingPage() {
      return prototypeApplicationPage(state.resumeRelation);
    },
    async findRelatedResume() {
      calls.increment("findRelatedResume");
      return existingResumeId
        ? { id: existingResumeId, name: "Engineer at Example" }
        : null;
    },
    async validateResumeWorkflowSchema() {
      return { valid: true, errors: [], warnings: [] };
    },
    async getPageChildren(pageId) {
      return pageId === "master-resume"
        ? masterBlocks
        : applicationBlocks;
    },
    async findMasterResumePages() {
      return masterPages;
    },
    async createUnlinkedJobSpecificResume(input) {
      calls.increment("createResume");
      effects.push("create_resume");
      state.resumes.push({ id: "resume-1", blocks: input.blocks, archived: false });
      return { id: "resume-1", name: input.resumeName };
    },
    async attachResumeToJobPosting() {
      calls.increment("attachResume");
      effects.push("attach_resume");
      if (attachFails) throw new Error("Attach failed.");
      state.resumeRelation = ["resume-1"];
      return { id: "resume-1", name: "Engineer at Example" };
    },
    async archiveResumePage(resumeId) {
      calls.increment("archiveResume");
      effects.push("archive_resume");
      const resume = state.resumes.find(({ id }) => id === resumeId);
      if (resume) resume.archived = true;
    },
  };
  const notesClient = {
    async validateNotesWorkflowSchema() {
      return { valid: true, errors: [], warnings: [] };
    },
    async createResumeFitAnalysisNote(input) {
      calls.increment("createNote");
      effects.push("create_note");
      if (noteFails) throw new Error("Note append failed.");
      state.notes.push({ id: "note-1", blocks: input.blocks, archived: false });
      return { id: "note-1", name: input.noteName };
    },
    async archiveNote(noteId) {
      calls.increment("archiveNote");
      effects.push("archive_note");
      const note = state.notes.find(({ id }) => id === noteId);
      if (note) note.archived = true;
    },
  };
  const pdfExporter = {
    async save(input) {
      calls.increment("savePdf");
      effects.push("save_pdf");
      if (pdfFails) throw new Error("PDF write failed.");
      const pdf = {
        id: "pdf-1",
        relativePath: "export/Example-ElizabethParnell.pdf",
        sourceBlocks: input.resumeBlocks,
      };
      state.pdfs.push(pdf);
      return pdf;
    },
    async remove(pdf) {
      calls.increment("removePdf");
      effects.push("remove_pdf");
      state.pdfs = state.pdfs.filter(({ id }) => id !== pdf.id);
      state.removedPdfs.push(pdf.id);
    },
  };

  return {
    effects,
    calls,
    state,
    initialResumeIds: new Set(existingResumeId ? [existingResumeId] : []),
    resumeClient,
    notesClient,
    pdfExporter,
  };
}

function normalizedResumeState(scenario) {
  return {
    resumes: scenario.state.resumes.map((resume) => ({
      id: resume.id,
      archived: resume.archived,
      headings: headings(resume.blocks),
      roleBulletCounts: roleBulletCounts(resume.blocks),
      containsFitAnalysis: headings(resume.blocks).includes("Resume Fit Analysis"),
    })),
    notes: scenario.state.notes.map((note) => ({
      id: note.id,
      archived: note.archived,
      headings: headings(note.blocks),
    })),
    pdfs: scenario.state.pdfs.map((pdf) => ({
      id: pdf.id,
      matchesResumeSource: pdf.sourceBlocks === scenario.state.resumes[0]?.blocks,
    })),
    resumeRelation: [...scenario.state.resumeRelation],
  };
}

function headings(blocks) {
  return blocks
    .filter((block) => block.type.startsWith("heading_"))
    .map(blockText);
}

function roleBulletCounts(blocks) {
  const counts = [];
  for (const block of blocks) {
    if (block.type === "heading_2" && blockText(block) !== "Summary") counts.push(0);
    if (block.type === "bulleted_list_item" && counts.length > 0) {
      counts[counts.length - 1] += 1;
    }
  }
  return counts;
}

function blockedFitAnalysis(calls) {
  return {
    async health() { return { ok: true }; },
    async analyze() {
      calls.increment("fitAnalysis");
      const error = new Error("Insufficient Master Resume evidence to create a truthful Job-Specific Resume.");
      error.reason = RESUME_FAILURE_REASONS.INSUFFICIENT_MASTER_RESUME_EVIDENCE;
      error.extra = {
        fitSummary: {
          evidenceItemCount: 20,
          supportedRequiredRequirementCount: 0,
          requiredRequirementCount: 1,
          supportedRequirementCount: 0,
          scoredRequirementCount: 1,
        },
      };
      throw error;
    },
  };
}

function forbiddenFitAnalysis(calls) {
  return {
    async health() {
      calls.increment("fitAnalysis");
      throw new Error("Fit analysis must not be called.");
    },
  };
}

function forbiddenResumeModel(calls) {
  return {
    async generateResume() {
      calls.increment("resumeModel");
      throw new Error("Resume model must not be called.");
    },
  };
}

function supportedFitAnalysis(calls) {
  return {
    async health() { return { ok: true }; },
    async analyze() {
      calls.increment("fitAnalysis");
      return { fitScore: supportedFitScore() };
    },
  };
}

function supportedFitScore({
  requirementId = "req-1",
  evidenceId = "evidence-3",
  evidenceOwner = "Software Engineer, ClinMatchGO",
} = {}) {
  return {
          ok: true,
          generationAllowed: true,
          overallFitScore: 0.82,
          categoryScores: [
            { category: "APIs & Integrations", fitScore: 0.82, requirementCount: 1 },
          ],
          requirements: [{
            requirementId,
            text: "Build REST APIs",
            type: "required skill",
            category: "APIs & Integrations",
            importance: "required",
            evidenceStrength: "direct evidence",
            matches: [{
              evidenceId,
              evidenceStrength: "direct evidence",
              evidenceText: "Built REST APIs backed by PostgreSQL 1.",
              sourceSection: evidenceOwner,
            }],
          }],
          gaps: [],
  };
}

function supportedResumeModel(calls) {
  return {
    async generateResume() {
      calls.increment("resumeModel");
      return {
        name: "Elizabeth Parnell",
        summary: "Engineer focused on reliable REST APIs.",
        skills: [],
        roles: [{
          templateId: "clinmatchgo-software-engineer",
          sourceSection: "Software Engineer, ClinMatchGO",
          heading: "Software Engineer, ClinMatchGO",
          title: "Software Engineer",
          organization: "ClinMatchGO",
          dateRange: "2025 - Present",
          bullets: ["Built REST APIs backed by PostgreSQL 1."],
          claimTraces: [{
            bulletIndex: 0,
            evidenceIds: ["evidence-3"],
            requirementIds: ["req-1"],
          }],
        }],
        sections: [],
      };
    },
  };
}

function prototypeApplicationPage(resumeRelation) {
  return {
    id: "application-1",
    properties: {
      "Company Name": richText("Example"),
      "Job Title": richText("Engineer"),
      "Application Status": { select: { name: "To Apply" } },
      Analyzed: { checkbox: true },
      Resumes: { type: "relation", relation: resumeRelation.map((id) => ({ id })) },
      Name: { title: [] },
    },
  };
}

function prototypeApplicationBlocks() {
  return [
    notionBlock("heading_2", "Job Content"),
    notionBlock("paragraph", "Build REST APIs with PostgreSQL."),
    notionBlock("heading_2", "Job Posting Analysis"),
    notionBlock("paragraph", "The role needs REST APIs and PostgreSQL."),
  ];
}

function prototypeMasterResumeBlocks(bulletCount = 5) {
  return [
    notionBlock("heading_2", "Work Experience"),
    notionBlock("heading_3", "Software Engineer, ClinMatchGO"),
    ...bullets("Built REST APIs backed by PostgreSQL", bulletCount),
    notionBlock("heading_3", "AI Studio Coach, Break Through Tech"),
    ...bullets("Coached student teams building applied ML apps", bulletCount),
    notionBlock("heading_3", "Lead Instructor, General Assembly"),
    ...bullets("Taught JavaScript React and MongoDB architecture", bulletCount),
    notionBlock("heading_3", "Software Engineer, Wayfair"),
    ...bullets("Supported gift card transaction reliability", bulletCount),
  ];
}

function bullets(prefix, count) {
  return Array.from({ length: count }, (_, index) => (
    notionBlock("bulleted_list_item", `${prefix} ${index + 1}.`)
  ));
}

function jobContentOnlyBlocks() {
  return [
    notionBlock("heading_2", "Job Content"),
    notionBlock("paragraph", "Build REST APIs with PostgreSQL."),
  ];
}

function analysisOnlyBlocks() {
  return [
    notionBlock("heading_2", "Job Posting Analysis"),
    notionBlock("paragraph", "The role needs REST APIs and PostgreSQL."),
  ];
}
