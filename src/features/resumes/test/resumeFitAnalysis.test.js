import test from "node:test";
import assert from "node:assert/strict";
import { ResumeFitAnalysis } from "../lib/resumeFitAnalysis.js";
import { RESUME_FAILURE_REASONS } from "../types/contracts.js";

test("ResumeFitAnalysis extracts requirements and returns one fit score result", async () => {
  const extractionCalls = [];
  const requirementExtractor = {
    async extractFitRequirements(input) {
      extractionCalls.push(input);
      return [fitRequirement()];
    },
  };
  const fitRuntimeClient = fakeFitRuntimeClient();
  const analysis = new ResumeFitAnalysis({
    requirementExtractor,
    fitRuntimeClient,
  });

  const result = await analysis.analyze({
    jobContent: "Build REST APIs with PostgreSQL.",
    jobPostingAnalysis: "The role needs REST APIs and PostgreSQL.",
    masterEvidenceItems: [masterEvidenceItem()],
  });

  assert.equal(result.fitScore.overallFitScore, 0.9);
  assert.equal(extractionCalls.length, 1);
  assert.equal(fitRuntimeClient.candidateCalls.length, 1);
  assert.equal(fitRuntimeClient.scoreCalls.length, 1);
  assert.deepEqual(fitRuntimeClient.scoreCalls[0].candidates, candidateMatches());
});

test("ResumeFitAnalysis validates extracted requirements against Job Content before scoring", async () => {
  const requirementExtractor = {
    async extractFitRequirements() {
      return [
        {
          ...fitRequirement(),
          evidence: "GraphQL",
          text: "Build GraphQL APIs",
        },
      ];
    },
  };
  const fitRuntimeClient = fakeFitRuntimeClient();
  const analysis = new ResumeFitAnalysis({
    requirementExtractor,
    fitRuntimeClient,
  });

  await assert.rejects(
    () => analysis.analyze({
      jobContent: "Build REST APIs with PostgreSQL.",
      jobPostingAnalysis: "The role needs REST APIs.",
      masterEvidenceItems: [masterEvidenceItem()],
    }),
    /Fit Requirement evidence was not found in Job Content/,
  );
  assert.equal(fitRuntimeClient.candidateCalls.length, 0);
  assert.equal(fitRuntimeClient.scoreCalls.length, 0);
});

test("ResumeFitAnalysis blocks generation with an insufficient evidence summary", async () => {
  const analysis = new ResumeFitAnalysis({
    requirementExtractor: {
      async extractFitRequirements() {
        return [fitRequirement()];
      },
    },
    fitRuntimeClient: fakeFitRuntimeClient({
      score: {
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
  });

  await assert.rejects(
    () => analysis.analyze({
      jobContent: "Build REST APIs with PostgreSQL.",
      jobPostingAnalysis: "The role needs REST APIs.",
      masterEvidenceItems: [masterEvidenceItem()],
    }),
    (error) => {
      assert.equal(error.reason, RESUME_FAILURE_REASONS.INSUFFICIENT_MASTER_RESUME_EVIDENCE);
      assert.equal(error.extra.fitSummary.supportedRequiredRequirementCount, 0);
      assert.equal(error.extra.fitSummary.requiredRequirementCount, 1);
      assert.equal(error.extra.fitSummary.evidenceItemCount, 1);
      return true;
    },
  );
});

test("ResumeFitAnalysis reports runtime health through its interface", async () => {
  const analysis = new ResumeFitAnalysis({
    requirementExtractor: {
      async extractFitRequirements() {
        return [];
      },
    },
    fitRuntimeClient: fakeFitRuntimeClient({
      health: { ok: false, message: "runtime unavailable" },
    }),
  });

  assert.deepEqual(await analysis.health(), { ok: false, message: "runtime unavailable" });
});

function fakeFitRuntimeClient({
  health = { ok: true },
  score = fitScore(),
} = {}) {
  return {
    candidateCalls: [],
    scoreCalls: [],
    async health() {
      return health;
    },
    async candidates(input) {
      this.candidateCalls.push(input);
      return {
        ok: true,
        candidates: candidateMatches(),
      };
    },
    async score(input) {
      this.scoreCalls.push(input);
      return score;
    },
  };
}

function fitRequirement() {
  return {
    id: "req-1",
    text: "Build REST APIs",
    type: "required skill",
    category: "APIs & Integrations",
    importance: "required",
    evidence: "REST APIs",
  };
}

function masterEvidenceItem() {
  return {
    id: "evidence-1",
    type: "bullet",
    sourceSection: "Software Engineer, ClinMatchGO",
    text: "Built REST APIs backed by PostgreSQL.",
  };
}

function candidateMatches() {
  return [
    {
      requirementId: "req-1",
      matches: [
        {
          evidenceId: "evidence-1",
          keywordCoverage: 0.9,
          tfidfSimilarity: 0.8,
          normalizedSkillOverlap: ["REST APIs"],
          sectionHint: false,
          score: 0.9,
        },
      ],
    },
  ];
}

function fitScore() {
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
            evidenceId: "evidence-1",
            evidenceStrength: "direct evidence",
            evidenceText: "Built REST APIs backed by PostgreSQL.",
            sourceSection: "Software Engineer, ClinMatchGO",
          },
        ],
      },
    ],
    gaps: [],
  };
}
