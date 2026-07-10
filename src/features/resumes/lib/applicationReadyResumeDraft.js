import { toPlainSingleLine } from "../../jobPostings/lib/text.js";
import {
  claimSupportedByEvidence,
  evidenceOverlapScore,
  findEvidenceIdsForClaim,
  normalizeEvidenceText,
} from "../../jobPostings/lib/evidenceSupport.js";
import {
  buildJobSpecificResumeBlocks,
  buildResumeFitAnalysisBlocks,
  extractMasterResumeWorkExperienceRoles,
} from "./resumeBlocks.js";
import { DeepSeekResumeClient } from "./deepseekResume.js";
import {
  missingResumeTemplateRoles,
  resumeTemplateRoleHeading,
} from "./resumeTemplate.js";
import { RESUME_FAILURE_REASONS } from "../types/contracts.js";

const ROLE_BULLET_MINIMUM = 5;
const ROLE_BULLET_PREFERRED = 6;
const ROLE_BULLET_MAXIMUM = 7;

export class ApplicationReadyResumeDraft {
  constructor({
    resumeGenerator,
  }) {
    this.resumeGenerator = resumeGenerator;
  }

  async create({
    resumeName,
    jobPosting,
    masterEvidenceItems,
    fitScore,
  }) {
    const evidenceItems = Array.isArray(masterEvidenceItems) ? masterEvidenceItems : [];
    if (evidenceItems.length === 0) {
      throw draftError(RESUME_FAILURE_REASONS.MISSING_MASTER_RESUME, "Master Resume must contain evidence before Resume generation.");
    }

    const workExperienceRoles = extractMasterResumeWorkExperienceRoles(evidenceItems);
    validateTemplateRoles(workExperienceRoles);

    const generatedResume = await this.resumeGenerator.generateResume({
      resumeName,
      jobPosting,
      masterEvidenceItems: evidenceItems,
      fitScore,
      workExperienceRoles,
    });
    const applicationReadyResume = prepareApplicationReadyResume(generatedResume, fitScore, {
      masterEvidenceItems: evidenceItems,
      workExperienceRoles,
    });

    const fitAnalysis = {
      summary: `Compared ${resumeName} against the Master Resume using Job Content as source of truth.`,
      score: fitScore,
    };
    const generatedResumeBlocksInput = {
      ...applicationReadyResume,
      name: applicationReadyResume.name || resumeName,
    };

    return {
      fitAnalysisBlocks: buildResumeFitAnalysisBlocks({ fitAnalysis }),
      resumeBlocks: buildJobSpecificResumeBlocks({ generatedResume: generatedResumeBlocksInput }),
    };
  }
}

export function createApplicationReadyResumeDraft({
  config = {},
  resumeGenerator,
  resumeLlm,
} = {}) {
  return new ApplicationReadyResumeDraft({
    resumeGenerator: resumeGenerator || resumeLlm || new DeepSeekResumeClient({
      apiKey: config.deepseekApiKey,
      model: config.deepseekModel,
    }),
  });
}

function validateTemplateRoles(workExperienceRoles) {
  const missingTemplateRoles = missingResumeTemplateRoles(workExperienceRoles);
  if (missingTemplateRoles.length > 0) {
    throw draftError(
      RESUME_FAILURE_REASONS.MISSING_MASTER_RESUME,
      `Master Resume is missing required template work experience section(s): ${missingTemplateRoles.map(resumeTemplateRoleHeading).join(", ")}.`,
    );
  }
}

function prepareApplicationReadyResume(generatedResume, fitScore, {
  masterEvidenceItems = [],
  workExperienceRoles = [],
} = {}) {
  const supportedRequirementIds = new Set(
    (fitScore.requirements || [])
      .filter(isDirectOrAdjacent)
      .map((requirement) => requirement.requirementId),
  );
  const supportedRequirements = [];
  const supportedRequirementById = new Map();
  const supportedEvidenceById = new Map();
  const requirementIdsByEvidenceId = new Map();
  const masterEvidenceById = new Map((masterEvidenceItems || []).map((item) => [item.id, item]));

  for (const requirement of fitScore.requirements || []) {
    if (!supportedRequirementIds.has(requirement.requirementId)) {
      continue;
    }
    supportedRequirements.push(requirement);
    supportedRequirementById.set(requirement.requirementId, requirement);

    for (const match of requirement.matches || []) {
      if (!isDirectOrAdjacent(match)) {
        continue;
      }
      supportedEvidenceById.set(match.evidenceId, match);
      if (!requirementIdsByEvidenceId.has(match.evidenceId)) {
        requirementIdsByEvidenceId.set(match.evidenceId, new Set());
      }
      requirementIdsByEvidenceId.get(match.evidenceId).add(requirement.requirementId);
    }
  }

  const roles = [];
  for (const role of generatedResume.roles || []) {
    const bullets = [];
    const claimTraces = [];

    for (let index = 0; index < (role.bullets || []).length; index += 1) {
      const bullet = role.bullets[index];
      const trace = (role.claimTraces || []).find((item) => item.bulletIndex === index);
      const repairedTrace = repairResumeBulletTrace({
        bullet,
        trace,
        masterEvidenceById,
        supportedRequirements,
        supportedRequirementById,
        supportedRequirementIds,
        requirementIdsByEvidenceId,
        nextBulletIndex: bullets.length,
      });

      if (!repairedTrace) {
        continue;
      }

      bullets.push(bullet);
      claimTraces.push(repairedTrace);
    }

    if (bullets.length > 0) {
      roles.push({
        ...role,
        sourceSection: role.sourceSection || "",
        bullets,
        claimTraces,
      });
    }
  }

  const applicationReadyRoles = completeWorkExperienceRoles({
    roles,
    masterEvidenceItems,
    workExperienceRoles,
    supportedEvidenceById,
    requirementIdsByEvidenceId,
  });

  const repairedBulletCount = applicationReadyRoles.reduce((count, role) => count + role.bullets.length, 0);
  if (repairedBulletCount === 0) {
    throw draftError(RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED, "Generated resume must include at least one bullet that maps to supported Master Resume evidence.");
  }

  return {
    ...generatedResume,
    roles: applicationReadyRoles,
  };
}

function completeWorkExperienceRoles({
  roles,
  masterEvidenceItems,
  workExperienceRoles,
  supportedEvidenceById,
  requirementIdsByEvidenceId,
}) {
  const evidenceById = new Map((masterEvidenceItems || []).map((item) => [item.id, item]));
  const roleTargets = (workExperienceRoles || [])
    .map((role) => ({
      ...role,
      allBulletEvidenceIds: uniqueStrings(role.bulletEvidenceIds)
        .filter((evidenceId) => evidenceById.has(evidenceId)),
    }))
    .filter((role) => role.allBulletEvidenceIds.length > 0);

  if (roleTargets.length === 0) {
    return roles.map((role) => limitRoleBullets(role));
  }

  const usedRoleIndexes = new Set();
  const completedRoles = [];

  for (const target of roleTargets) {
    const roleIndex = findMatchingRoleIndex({ roles, target, usedRoleIndexes });
    const sourceRole = roleIndex >= 0
      ? roles[roleIndex]
      : {
        heading: target.heading,
        sourceSection: target.sourceSection,
        bullets: [],
        claimTraces: [],
      };

    if (roleIndex >= 0) {
      usedRoleIndexes.add(roleIndex);
    }

    const role = filterRoleToTargetEvidence(limitRoleBullets({
      ...sourceRole,
      heading: target.heading,
      sourceSection: target.sourceSection,
      templateId: target.templateId,
      title: target.title,
      organization: target.organization,
      dateRange: target.dateRange,
    }), target);
    const hasSupportedRoleEvidence = target.allBulletEvidenceIds
      .some((evidenceId) => supportedEvidenceById.has(evidenceId));
    const preferredBulletCount = Math.min(
      hasSupportedRoleEvidence ? ROLE_BULLET_PREFERRED : ROLE_BULLET_MINIMUM,
      target.allBulletEvidenceIds.length,
    );

    fillRoleFromMasterEvidence({
      role,
      target,
      evidenceById,
      requirementIdsByEvidenceId,
      supportedEvidenceById,
      preferredBulletCount,
    });

    if (role.bullets.length < ROLE_BULLET_MINIMUM) {
      throw draftError(
        RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED,
        `Generated resume role "${target.heading}" has ${role.bullets.length} evidence-backed bullet(s); expected at least ${ROLE_BULLET_MINIMUM}.`,
      );
    }

    completedRoles.push({
      ...limitRoleBullets(role),
      templateId: target.templateId,
      heading: target.heading,
      title: target.title,
      organization: target.organization,
      dateRange: target.dateRange,
    });
  }

  return completedRoles;
}

function fillRoleFromMasterEvidence({
  role,
  target,
  evidenceById,
  requirementIdsByEvidenceId,
  supportedEvidenceById,
  preferredBulletCount,
}) {
  const existingTexts = new Set(role.bullets.map(normalizeComparableText));
  const existingEvidenceIds = new Set(role.claimTraces.flatMap((trace) => trace.evidenceIds || []));
  const rankedEvidenceIds = rankTargetEvidenceIds(target, supportedEvidenceById);

  if (target.allBulletEvidenceIds.length < ROLE_BULLET_MINIMUM) {
    throw draftError(
      RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED,
      `Master Resume role "${target.heading}" has only ${target.allBulletEvidenceIds.length} bullet evidence item(s); at least ${ROLE_BULLET_MINIMUM} are required for an application-ready Resume.`,
    );
  }

  for (const evidenceId of rankedEvidenceIds) {
    if (role.bullets.length >= preferredBulletCount || role.bullets.length >= ROLE_BULLET_MAXIMUM) {
      break;
    }
    if (existingEvidenceIds.has(evidenceId)) {
      continue;
    }

    const evidence = evidenceById.get(evidenceId);
    const bullet = toPlainSingleLine(evidence?.text || "", 400);
    const comparable = normalizeComparableText(bullet);
    const requirementIds = uniqueStrings([...(requirementIdsByEvidenceId.get(evidenceId) || [])]);

    if (!bullet || existingTexts.has(comparable)) {
      continue;
    }

    role.bullets.push(bullet);
    role.claimTraces.push({
      bulletIndex: role.bullets.length - 1,
      evidenceIds: [evidenceId],
      requirementIds: requirementIds.slice(0, 3),
    });
    existingTexts.add(comparable);
    existingEvidenceIds.add(evidenceId);
  }
}

function filterRoleToTargetEvidence(role, target) {
  const targetEvidenceIds = new Set(target.allBulletEvidenceIds);
  const bullets = [];
  const claimTraces = [];

  for (let index = 0; index < role.bullets.length; index += 1) {
    const trace = (role.claimTraces || []).find((item) => item.bulletIndex === index);
    const evidenceIds = uniqueStrings(trace?.evidenceIds)
      .filter((evidenceId) => targetEvidenceIds.has(evidenceId));

    if (evidenceIds.length === 0) {
      continue;
    }

    bullets.push(role.bullets[index]);
    claimTraces.push({
      ...trace,
      bulletIndex: bullets.length - 1,
      evidenceIds,
    });
  }

  return {
    ...role,
    bullets,
    claimTraces,
  };
}

function rankTargetEvidenceIds(target, supportedEvidenceById) {
  const ids = uniqueStrings(target.allBulletEvidenceIds);
  const supported = ids.filter((evidenceId) => supportedEvidenceById.has(evidenceId));
  const unsupported = ids.filter((evidenceId) => !supportedEvidenceById.has(evidenceId));

  return [...supported, ...unsupported];
}

function limitRoleBullets(role) {
  const bullets = (role.bullets || []).slice(0, ROLE_BULLET_MAXIMUM);
  const traces = [];

  for (let index = 0; index < bullets.length; index += 1) {
    const trace = (role.claimTraces || []).find((item) => item.bulletIndex === index);
    if (trace) {
      traces.push({
        ...trace,
        bulletIndex: index,
      });
    }
  }

  return {
    ...role,
    bullets,
    claimTraces: traces,
  };
}

function findMatchingRoleIndex({ roles, target, usedRoleIndexes }) {
  const targetSource = normalizeRoleText(target.sourceSection);
  const targetHeading = normalizeRoleText(target.heading);

  for (let index = 0; index < roles.length; index += 1) {
    if (usedRoleIndexes.has(index)) {
      continue;
    }

    const role = roles[index];
    const source = normalizeRoleText(role.sourceSection);
    const heading = normalizeRoleText(role.heading);

    if ((source && source === targetSource) || (heading && heading === targetHeading)) {
      return index;
    }

    if (roleTextIncludes(heading, targetHeading) || roleTextIncludes(targetHeading, heading)) {
      return index;
    }
  }

  return -1;
}

function roleTextIncludes(left, right) {
  return Boolean(left && right && right.length >= 8 && left.includes(right));
}

function repairResumeBulletTrace({
  bullet,
  trace,
  masterEvidenceById,
  supportedRequirements,
  supportedRequirementById,
  supportedRequirementIds,
  requirementIdsByEvidenceId,
  nextBulletIndex,
}) {
  const tracedRequirementIds = uniqueStrings(trace?.requirementIds)
    .filter((id) => supportedRequirementIds.has(id));
  const tracedEvidenceIds = uniqueStrings(trace?.evidenceIds)
    .filter((id) => masterEvidenceById.has(id));

  let evidenceIds = tracedEvidenceIds.length > 0
    ? tracedEvidenceIds
    : bestMasterEvidenceIdsForBullet(bullet, masterEvidenceById);

  if (evidenceIds.length > 0 && !isBulletSupportedByEvidence(bullet, evidenceIds, masterEvidenceById)) {
    evidenceIds = bestMasterEvidenceIdsForBullet(bullet, masterEvidenceById);
  }

  if (evidenceIds.length === 0 || !isBulletSupportedByEvidence(bullet, evidenceIds, masterEvidenceById)) {
    return null;
  }

  const requirementIds = uniqueStrings([
    ...tracedRequirementIds,
    ...requirementIdsForEvidence(evidenceIds, requirementIdsByEvidenceId),
    ...bestSupportedRequirementIdsForBullet(bullet, supportedRequirements),
  ])
    .filter((requirementId) => supportedRequirementById.has(requirementId));

  return {
    bulletIndex: nextBulletIndex,
    evidenceIds: evidenceIds.slice(0, 3),
    requirementIds: requirementIds.slice(0, 3),
  };
}

function bestMasterEvidenceIdsForBullet(bullet, masterEvidenceById) {
  return findEvidenceIdsForClaim(
    bullet,
    [...masterEvidenceById.values()].filter((item) => item.type === "bullet"),
  );
}

function isBulletSupportedByEvidence(bullet, evidenceIds, masterEvidenceById) {
  return claimSupportedByEvidence(
    bullet,
    evidenceIds.map((evidenceId) => masterEvidenceById.get(evidenceId)?.text || ""),
  );
}

function requirementIdsForEvidence(evidenceIds, requirementIdsByEvidenceId) {
  const output = [];
  for (const evidenceId of evidenceIds) {
    output.push(...(requirementIdsByEvidenceId.get(evidenceId) || []));
  }
  return uniqueStrings(output);
}

function bestSupportedRequirementIdsForBullet(bullet, supportedRequirements) {
  return supportedRequirements
    .map((requirement) => ({
      id: requirement.requirementId,
      score: Math.max(
        evidenceOverlapScore(bullet, requirement.text),
        ...((requirement.matches || []).map((match) => evidenceOverlapScore(bullet, match.evidenceText))),
      ),
    }))
    .filter((item) => item.score >= 0.2)
    .sort((left, right) => right.score - left.score)
    .slice(0, 2)
    .map((item) => item.id);
}

function isDirectOrAdjacent(item) {
  return item.evidenceStrength === "direct evidence" || item.evidenceStrength === "adjacent evidence";
}

function uniqueStrings(values) {
  return [...new Set((Array.isArray(values) ? values : [])
    .map((value) => String(value || "").trim())
    .filter(Boolean))];
}

function normalizeComparableText(value) {
  return normalizeEvidenceText(value);
}

function normalizeRoleText(value) {
  return normalizeEvidenceText(value);
}

function draftError(reason, message, extra = {}) {
  const error = new Error(message);
  error.reason = reason;
  error.extra = extra;
  return error;
}
