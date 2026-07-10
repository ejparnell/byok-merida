import { createCaptureEvidence } from "../../../src/features/jobPostings/lib/captureEvidence.js";
import {
  captureJobPosting,
  confirmJobPosting,
  prepareJobPostingReview,
} from "../../../src/features/jobPostings/backend/captureService.js";
import { buildPageProperties } from "../../../src/features/jobPostings/lib/notion.js";
import { buildJobPostingBlocks } from "../../../src/features/jobPostings/lib/notionBlocks.js";
import { blockText, createCallCounter } from "./observerSupport.js";

export async function observeCaptureFixture(fixture) {
  switch (fixture.observation.runner) {
    case "capture_evidence":
      return observeCaptureEvidence(fixture);
    case "capture_duplicate":
      return observeCaptureDuplicate(fixture);
    case "capture_parse_only":
      return observeCaptureParseOnly(fixture);
    case "capture_outcome_matrix":
      return observeCaptureOutcomeMatrix(fixture);
    default:
      throw new Error(`Unsupported Capture runner: ${fixture.observation.runner}`);
  }
}

async function observeCaptureOutcomeMatrix(fixture) {
  const effects = [];
  const calls = createCallCounter();
  const records = [];
  const dependencies = fixture.observation.dependencyOutputs;
  const client = (caseName) => ({
    async validateDatabaseSchema() {
      calls.increment("validateDatabaseSchema");
      effects.push(`${caseName}:validate_schema`);
      return dependencies.schemaByCase[caseName] === "valid"
        ? { valid: true, errors: [], warnings: [] }
        : { valid: false, errors: ["Bad schema"], warnings: [] };
    },
    async findExistingJobPosting() {
      calls.increment("findExistingJobPosting");
      effects.push(`${caseName}:find_by_canonical_job_url`);
      const existingApplicationId = dependencies.duplicateByCase[caseName];
      return existingApplicationId
        ? { id: existingApplicationId, url: `https://notion.so/${existingApplicationId}` }
        : null;
    },
    async createJobPostingPage(parsed, now) {
      calls.increment("createJobPostingPage");
      effects.push(`${caseName}:create_application`);
      if (dependencies.writeByCase[caseName] === "failure") {
        throw new Error("Workspace write failed.");
      }
      const properties = buildPageProperties(parsed);
      const { blocks } = buildJobPostingBlocks(parsed, now);
      const record = {
        caseName,
        jobUrl: properties["Job URL"].url,
        applicationStatus: properties["Application Status"].select.name,
        analyzed: properties.Analyzed.checkbox,
        matchScorePresent: "Match Score" in properties,
        applicationDatePresent: "Application Date" in properties,
        headings: blocks
          .filter((block) => block.type.startsWith("heading_"))
          .map(blockText)
          .filter((heading) => ["Capture Summary", "Job Content"].includes(heading)),
      };
      records.push(record);
      return { id: `${caseName}-application`, url: `https://notion.so/${caseName}` };
    },
  });
  const inputs = fixture.observation.initialState;
  const now = new Date("2026-01-01T00:00:00.000Z");
  const created = await captureJobPosting(inputs.strongEvidence, {
    notionClient: client("created"),
    now,
  });
  const needsReview = await captureJobPosting(inputs.weakEvidence, {
    notionClient: client("review"),
    now,
  });
  const missingContent = await captureJobPosting(inputs.missingContentEvidence, {
    notionClient: client("missing_content"),
    now,
  });
  const missingUrl = await captureJobPosting(inputs.missingUrlEvidence, {
    notionClient: client("missing_url"),
    now,
  });
  const invalidSchema = await captureJobPosting(inputs.strongEvidence, {
    notionClient: client("invalid_schema"),
    now,
  });
  const confirmed = await confirmJobPosting(inputs.confirmedApplication, {
    notionClient: client("confirmed"),
    now,
  });
  let writeFailure = "not_observed";
  try {
    await captureJobPosting(inputs.strongEvidence, {
      notionClient: client("write_failure"),
      now,
    });
  } catch {
    writeFailure = "threw";
  }

  return {
    outcome: {
      created: created.type,
      needsReview: needsReview.type,
      missingContent: missingContent.type,
      missingUrl: missingUrl.type,
      invalidSchema: invalidSchema.type,
      confirmed: confirmed.type,
      writeFailure,
    },
    effects,
    state: { records },
    callCounts: calls.snapshot([
      "validateDatabaseSchema",
      "findExistingJobPosting",
      "createJobPostingPage",
    ]),
    cleanupResidue: { createdApplications: records.length },
  };
}

function observeCaptureEvidence(fixture) {
  const evidence = createCaptureEvidence(fixture.observation.initialState);
  const oversizedEvidence = createCaptureEvidence({
    url: fixture.observation.initialState.tabUrl,
    visibleText: "x".repeat(fixture.observation.dependencyOutputs.oversizedVisibleTextLength),
  });
  const outcome = {
    jobUrl: evidence.jobUrl,
    capturedUrl: evidence.capturedUrl,
    companyName: evidence.structuredMetadata.companyName,
    role: evidence.structuredMetadata.jobTitle,
    location: evidence.structuredMetadata.location,
    preferredTextSource: evidence.content.selectedText ? "selectedText" : "visibleText",
    frameCount: evidence.summary.frameCount,
    oversizedVisibleTextLength: oversizedEvidence.content.visibleText.length,
    oversizedWarnings: oversizedEvidence.summary.validationWarnings,
  };

  return {
    outcome,
    effects: [],
    state: {
      normalizedEvidence: {
        jobUrl: evidence.jobUrl,
        capturedUrl: evidence.capturedUrl,
        hasSelectedText: Boolean(evidence.content.selectedText),
        hasVisibleText: Boolean(evidence.content.visibleText),
        frameCount: evidence.summary.frameCount,
        oversizedVisibleTextLength: oversizedEvidence.content.visibleText.length,
      },
    },
    callCounts: {},
    cleanupResidue: {},
  };
}

async function observeCaptureDuplicate(fixture) {
  const effects = [];
  const calls = createCallCounter();
  const existingApplicationId = fixture.observation.initialState.existingApplicationId;
  const state = {
    applications: [{ id: existingApplicationId, jobUrl: "https://example.com/jobs/123" }],
  };
  const notionClient = {
    async validateDatabaseSchema() {
      calls.increment("validateDatabaseSchema");
      effects.push("validate_schema");
      return { valid: true, errors: [], warnings: [] };
    },
    async findExistingJobPosting() {
      calls.increment("findExistingJobPosting");
      effects.push("find_by_canonical_job_url");
      return { id: existingApplicationId, url: `https://notion.so/${existingApplicationId}` };
    },
    async createJobPostingPage(parsed) {
      calls.increment("createJobPostingPage");
      effects.push("create_application");
      state.applications.push({ id: "unexpected-application", jobUrl: parsed.jobUrl });
      return { id: "unexpected-application" };
    },
  };

  const result = await captureJobPosting(fixture.observation.initialState.evidence, {
    notionClient,
    now: new Date("2026-01-01T00:00:00.000Z"),
  });

  return {
    outcome: { type: result.type, applicationId: result.page?.id || null },
    effects,
    state,
    callCounts: calls.snapshot([
      "validateDatabaseSchema",
      "findExistingJobPosting",
      "createJobPostingPage",
    ]),
    cleanupResidue: {
      createdApplications: state.applications.filter(({ id }) => id !== existingApplicationId).length,
    },
  };
}

function observeCaptureParseOnly(fixture) {
  const result = prepareJobPostingReview(fixture.observation.initialState.evidence);

  return {
    outcome: {
      type: result.type,
      jobUrl: result.parsed.jobUrl,
      companyName: result.parsed.companyName,
      role: result.parsed.jobTitle,
      hasJobContent: Boolean(result.parsed.jobContent),
    },
    effects: [],
    state: { workspace: { applications: [] } },
    callCounts: {},
    cleanupResidue: { workspaceCalls: 0 },
  };
}
