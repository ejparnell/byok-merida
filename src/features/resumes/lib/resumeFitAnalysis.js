import { textSupportsEvidence } from "../../jobPostings/lib/evidenceSupport.js";
import { RESUME_FAILURE_REASONS } from "../types/contracts.js";
import { DeepSeekResumeClient } from "./deepseekResume.js";
import { FitRuntimeClient } from "./fitRuntime.js";

export class ResumeFitAnalysis {
  constructor({
    requirementExtractor,
    fitRuntimeClient,
  }) {
    this.requirementExtractor = requirementExtractor;
    this.fitRuntimeClient = fitRuntimeClient;
  }

  async health() {
    return this.fitRuntimeClient.health();
  }

  async analyze({
    jobContent,
    jobPostingAnalysis,
    masterEvidenceItems,
  }) {
    const evidenceItems = Array.isArray(masterEvidenceItems) ? masterEvidenceItems : [];
    const requirements = await this.requirementExtractor.extractFitRequirements({
      jobContent,
      jobPostingAnalysis,
    });
    validateRequirementsAgainstJobContent(requirements, jobContent);

    const candidatePayload = await this.fitRuntimeClient.candidates({
      requirements,
      evidenceItems,
    });
    const candidates = candidatePayload.candidates || [];
    const fitScore = await this.fitRuntimeClient.score({
      requirements,
      evidenceItems,
      candidates,
    });

    if (!fitScore.generationAllowed) {
      const fitSummary = summarizeInsufficientEvidence({
        fitScore,
        evidenceItemCount: evidenceItems.length,
        requirementCount: requirements.length,
      });
      throw fitAnalysisError(
        RESUME_FAILURE_REASONS.INSUFFICIENT_MASTER_RESUME_EVIDENCE,
        insufficientEvidenceMessage(fitSummary),
        { fitSummary },
      );
    }

    return { fitScore };
  }
}

export function createResumeFitAnalysis({
  config = {},
  fitRuntimeClient,
  requirementExtractor,
  resumeLlm,
} = {}) {
  return new ResumeFitAnalysis({
    requirementExtractor: requirementExtractor || resumeLlm || new DeepSeekResumeClient({
      apiKey: config.deepseekApiKey,
      model: config.deepseekModel,
    }),
    fitRuntimeClient: fitRuntimeClient || new FitRuntimeClient({ baseUrl: config.fitRuntimeUrl }),
  });
}

function validateRequirementsAgainstJobContent(requirements, jobContent) {
  for (const requirement of requirements) {
    if (!requirement.evidence && !requirement.text) {
      throw fitAnalysisError(RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED, "Fit Requirement is missing evidence text.");
    }

    if (textSupportsEvidence(jobContent, {
      evidence: requirement.evidence,
      alternateEvidence: requirement.text,
      minTokenRatio: 0.6,
      requireAllTokensWhenShort: false,
      stopwords: new Set(),
      shortTokens: new Set(),
      wholeToken: false,
    })) {
      continue;
    }

    throw fitAnalysisError(RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED, `Fit Requirement evidence was not found in Job Content: ${requirement.evidence}`);
  }
}

function summarizeInsufficientEvidence({ fitScore, evidenceItemCount, requirementCount }) {
  const requirements = fitScore.requirements || [];
  const supported = requirements.filter(isDirectOrAdjacent);
  const required = requirements.filter(isRequiredOrResponsibility);
  const supportedRequired = required.filter(isDirectOrAdjacent);
  const counts = {
    "direct evidence": 0,
    "adjacent evidence": 0,
    "weak evidence": 0,
    "no evidence": 0,
  };

  for (const requirement of requirements) {
    counts[requirement.evidenceStrength] = (counts[requirement.evidenceStrength] || 0) + 1;
  }

  return {
    overallFitScore: fitScore.overallFitScore || 0,
    evidenceItemCount,
    requirementCount,
    scoredRequirementCount: requirements.length || requirementCount,
    supportedRequirementCount: supported.length,
    requiredRequirementCount: required.length,
    supportedRequiredRequirementCount: supportedRequired.length,
    evidenceStrengthCounts: counts,
    topGaps: (fitScore.gaps || []).slice(0, 5).map((gap) => ({
      text: gap.text || "",
      evidenceStrength: gap.evidenceStrength || "no evidence",
    })),
  };
}

function insufficientEvidenceMessage(summary) {
  return [
    "Insufficient Master Resume evidence to create a truthful Job-Specific Resume.",
    `Found ${summary.supportedRequiredRequirementCount}/${summary.requiredRequirementCount} required or responsibility requirements with direct/adjacent evidence`,
    `and ${summary.supportedRequirementCount}/${summary.scoredRequirementCount} total supported requirements`,
    `from ${summary.evidenceItemCount} Master Resume evidence item(s).`,
  ].join(" ");
}

function isRequiredOrResponsibility(requirement) {
  const importance = String(requirement.importance || "").toLowerCase();
  const type = String(requirement.type || "").toLowerCase();
  return importance === "required" || type.includes("required") || type.includes("responsibility");
}

function isDirectOrAdjacent(requirement) {
  return requirement.evidenceStrength === "direct evidence" || requirement.evidenceStrength === "adjacent evidence";
}

function fitAnalysisError(reason, message, extra = {}) {
  const error = new Error(message);
  error.reason = reason;
  error.extra = extra;
  return error;
}
