import { toPlainSingleLine } from "../../jobPostings/lib/text.js";
import { DeepSeekJsonClient } from "../../../backend/deepseekJson.js";
import { resumeTemplateMarkdown } from "./resumeTemplate.js";

export class DeepSeekResumeClient {
  constructor({
    apiKey,
    model,
    fetchImpl = fetch,
    logger = console,
  }) {
    this.deepseek = new DeepSeekJsonClient({
      apiKey,
      model,
      fetchImpl,
      logger,
      logPrefix: "resume-generation",
      missingApiKeyMessage: "DEEPSEEK_API_KEY is required for Resume generation.",
    });
  }

  async extractFitRequirements({ jobContent, jobPostingAnalysis }) {
    const { json } = await this.deepseek.requestJson({
      maxTokens: 4000,
      label: "fit-requirements",
      messagesForAttempt: ({ retry }) => requirementMessages({ jobContent, jobPostingAnalysis, retry }),
    });
    return validateRequirementsPayload(json, { jobContent });
  }

  async generateResume({ resumeName, jobPosting, masterEvidenceItems, fitScore, workExperienceRoles = [] }) {
    const { json } = await this.deepseek.requestJson({
      maxTokens: 8000,
      label: "resume-generation",
      messagesForAttempt: ({ retry }) => resumeMessages({ resumeName, jobPosting, masterEvidenceItems, fitScore, workExperienceRoles, retry }),
    });
    return validateGeneratedResumePayload(json);
  }
}

function requirementMessages({ jobContent, jobPostingAnalysis, retry }) {
  return [
    {
      role: "system",
      content: [
        "You extract concrete Fit Requirements for resume tailoring.",
        "Return strict JSON only.",
        "Use Job Content as source of truth and Job Posting Analysis only as supporting structure.",
        "Each requirement must include a short evidence phrase found in Job Content.",
        "Mark requirements as required when their evidence appears under Responsibilities, Requirements, Required Qualifications, Minimum Qualifications, What you will do, or must-have language.",
        "Mark requirements as preferred only when their evidence appears under Preferred Qualifications, Nice to have, Bonus, or similar optional language.",
        "Do not create standalone vague traits unless tied to concrete work.",
        retry ? "Your previous response was empty; return one non-empty JSON object now." : "",
      ].join(" "),
    },
    {
      role: "user",
      content: [
        "Return JSON in this shape:",
        "{",
        "  \"requirements\": [",
        "    {",
        "      \"id\": \"req-1\",",
        "      \"text\": \"Build REST APIs\",",
        "      \"type\": \"required skill\",",
        "      \"category\": \"APIs & Integrations\",",
        "      \"importance\": \"required\",",
        "      \"evidence\": \"REST APIs\"",
        "    }",
        "  ]",
        "}",
        "",
        "Allowed type values: responsibility, required skill, preferred skill, tool/technology, seniority signal, domain signal, work-style signal, qualification.",
        "Allowed importance values: required, preferred, signal.",
        "",
        "Job Posting Analysis:",
        jobPostingAnalysis,
        "",
        "Job Content:",
        jobContent,
      ].join("\n"),
    },
  ];
}

function resumeMessages({ resumeName, jobPosting, masterEvidenceItems, fitScore, workExperienceRoles, retry }) {
  const jobSupportedEvidenceIds = supportedEvidenceIds(fitScore);
  const supportedRequirementIds = supportedFitRequirementIds(fitScore);
  const workExperienceTargets = buildWorkExperienceTargets({
    workExperienceRoles,
    jobSupportedEvidenceIds,
  });

  return [
    {
      role: "system",
      content: [
        "You draft complete, application-ready, evidence-grounded job-specific resumes.",
        "Return strict JSON only.",
        "Use only Master Resume evidence.",
        "Preserve truthful ownership, role chronology, and standard resume structure.",
        "Do not invent metrics, tools, employers, titles, or chronology.",
        "Every bullet must include claimTraces referencing evidenceIds.",
        "Use requirementIds only when the bullet supports one of the supported requirement ids.",
        "Only cite evidenceIds from the Master Resume evidence list and requirementIds from the supported requirement list.",
        "The output must be a tailored resume someone can apply with, not only a fit-analysis summary.",
        "Every generated resume must follow the fixed Elizabeth Parnell resume template exactly.",
        retry ? "Your previous response was empty; return one non-empty JSON object now." : "",
      ].join(" "),
    },
    {
      role: "user",
      content: [
        "Return JSON in this shape:",
        "{",
        "  \"resume\": {",
        "    \"name\": \"Elizabeth Parnell\",",
        "    \"summary\": \"Targeted summary\",",
        "    \"skills\": [],",
        "    \"roles\": [",
        "      {",
        "        \"templateId\": \"clinmatchgo-software-engineer\",",
        "        \"sourceSection\": \"Exact Master Resume sourceSection for this role\",",
        "        \"heading\": \"Software Engineer, ClinMatchGO\",",
        "        \"title\": \"Software Engineer\",",
        "        \"organization\": \"ClinMatchGO\",",
        "        \"dateRange\": \"2025 - Present\",",
        "        \"bullets\": [\"Built REST APIs...\"],",
        "        \"claimTraces\": [",
        "          { \"bulletIndex\": 0, \"evidenceIds\": [\"evidence-1\"], \"requirementIds\": [\"req-1\"] }",
        "        ]",
        "      }",
        "    ],",
        "    \"sections\": []",
        "  }",
        "}",
        "",
        "Resume-writing rules:",
        "- Fill only the Summary and the Work Experience bullets in the fixed template.",
        "- Do not add Skills or extra sections to the rendered resume; leave skills and sections empty in JSON.",
        "- Use Work Experience Role Targets as the required role skeleton when targets are provided.",
        "- Include one role for every Work Experience Role Target.",
        "- Set each role.templateId exactly to the target templateId.",
        "- Set each role.sourceSection exactly to the target sourceSection.",
        "- Set each role title, organization, dateRange, and heading exactly from the target.",
        "- Preserve target role order. Do not invent roles or reorder chronology.",
        "- Keep every role's bullets tied to that role's allBulletEvidenceIds; do not move evidence from one work experience into another template slot.",
        "- Each work experience role should have 5 to 7 bullets; prefer 6 bullets.",
        "- Use jobSupportedBulletEvidenceIds first for job-specific emphasis.",
        "- Fill remaining role bullets from allBulletEvidenceIds so each role reaches at least 5 bullets.",
        "- Never exceed 7 bullets for any role.",
        "- Make bullets employer-facing and concise while preserving truthful source evidence.",
        "",
        "Fixed Resume Template:",
        resumeTemplateMarkdown(),
        "",
        `Resume Name: ${resumeName}`,
        `Job Posting: ${jobPosting.jobTitle || ""} at ${jobPosting.companyName || ""}`,
        "",
        "Fit Score JSON:",
        JSON.stringify(fitScore).slice(0, 16000),
        "",
        "Supported Fit Requirement IDs:",
        JSON.stringify(supportedRequirementIds),
        "",
        "Work Experience Role Targets:",
        JSON.stringify(workExperienceTargets),
        "",
        "Master Resume Evidence Items:",
        JSON.stringify(masterEvidenceItems || []).slice(0, 30000),
      ].join("\n"),
    },
  ];
}

function buildWorkExperienceTargets({ workExperienceRoles, jobSupportedEvidenceIds }) {
  const supportedIds = jobSupportedEvidenceIds || new Set();

  return (workExperienceRoles || [])
    .map((role) => {
      const allBulletEvidenceIds = role.bulletEvidenceIds || [];
      const jobSupportedBulletEvidenceIds = allBulletEvidenceIds
        .filter((evidenceId) => supportedIds.has(evidenceId));

      return {
        templateId: role.templateId,
        sourceSection: role.sourceSection,
        heading: role.heading,
        title: role.title,
        organization: role.organization,
        dateRange: role.dateRange,
        allBulletEvidenceIds,
        jobSupportedBulletEvidenceIds,
        availableMasterBulletCount: allBulletEvidenceIds.length,
        minimumBulletCount: 5,
        preferredBulletCount: 6,
        maximumBulletCount: 7,
      };
    })
    .filter((role) => role.availableMasterBulletCount > 0);
}

function supportedEvidenceIds(fitScore) {
  const evidenceIds = new Set();
  for (const requirement of fitScore.requirements || []) {
    if (!isSupportedRequirement(requirement)) {
      continue;
    }
    for (const match of requirement.matches || []) {
      if (match.evidenceStrength === "direct evidence" || match.evidenceStrength === "adjacent evidence") {
        evidenceIds.add(match.evidenceId);
      }
    }
  }
  return evidenceIds;
}

function supportedFitRequirementIds(fitScore) {
  return (fitScore.requirements || [])
    .filter(isSupportedRequirement)
    .map((requirement) => requirement.requirementId);
}

function isSupportedRequirement(requirement) {
  return requirement.evidenceStrength === "direct evidence" || requirement.evidenceStrength === "adjacent evidence";
}

function validateRequirementsPayload(payload, { jobContent = "" } = {}) {
  const requirements = Array.isArray(payload?.requirements) ? payload.requirements : [];
  return requirements.map((requirement, index) => {
    const type = normalizeRequirementType(requirement.type);
    const evidence = requiredText(requirement.evidence, "Fit Requirement evidence");
    const baseImportance = normalizeImportance(requirement.importance, type);

    return {
      id: toPlainSingleLine(requirement.id || `req-${index + 1}`, 80),
      text: requiredText(requirement.text, "Fit Requirement text"),
      type,
      category: toPlainSingleLine(requirement.category || requirement.type || "Other", 120),
      importance: normalizeContextualImportance({
        importance: baseImportance,
        evidence,
        jobContent,
      }),
      evidence,
    };
  });
}

function validateGeneratedResumePayload(payload) {
  const resume = payload?.resume || {};
  return {
    name: toPlainSingleLine(resume.name || "", 160),
    summary: toPlainSingleLine(resume.summary || "", 900),
    skills: arrayOfStrings(resume.skills, 80),
    roles: (Array.isArray(resume.roles) ? resume.roles : []).map((role) => ({
      templateId: toPlainSingleLine(role.templateId || "", 80),
      sourceSection: toPlainSingleLine(role.sourceSection || "", 180),
      heading: toPlainSingleLine(role.heading || "", 180),
      title: toPlainSingleLine(role.title || "", 120),
      organization: toPlainSingleLine(role.organization || "", 120),
      dateRange: toPlainSingleLine(role.dateRange || "", 80),
      bullets: arrayOfStrings(role.bullets, 400),
      claimTraces: validateClaimTraces(role.claimTraces),
    })).filter((role) => role.heading || role.bullets.length > 0),
    sections: (Array.isArray(resume.sections) ? resume.sections : []).map((section) => ({
      heading: toPlainSingleLine(section.heading || "", 120),
      items: arrayOfStrings(section.items, 300),
    })).filter((section) => section.heading || section.items.length > 0),
  };
}

function validateClaimTraces(traces) {
  return (Array.isArray(traces) ? traces : []).map((trace) => ({
    bulletIndex: Number.isInteger(trace.bulletIndex) ? trace.bulletIndex : 0,
    evidenceIds: arrayOfStrings(trace.evidenceIds, 80),
    requirementIds: arrayOfStrings(trace.requirementIds, 80),
  }));
}

function requiredText(value, label) {
  const text = toPlainSingleLine(value, 500);
  if (!text) {
    throw new Error(`${label} is required.`);
  }
  return text;
}

function arrayOfStrings(values, maxLength) {
  return (Array.isArray(values) ? values : [])
    .map((value) => toPlainSingleLine(value, maxLength))
    .filter(Boolean);
}

function normalizeRequirementType(value) {
  const type = String(value || "").toLowerCase();
  const allowed = new Set([
    "responsibility",
    "required skill",
    "preferred skill",
    "tool/technology",
    "seniority signal",
    "domain signal",
    "work-style signal",
    "qualification",
  ]);
  return allowed.has(type) ? type : "responsibility";
}

function normalizeImportance(value, type) {
  const importance = String(value || "").toLowerCase();
  if (importance === "required" || importance === "preferred" || importance === "signal") {
    return importance;
  }
  if (String(type || "").toLowerCase().includes("required") || String(type || "").toLowerCase() === "responsibility") {
    return "required";
  }
  if (String(type || "").toLowerCase().includes("preferred")) {
    return "preferred";
  }
  return "signal";
}

function normalizeContextualImportance({ importance, evidence, jobContent }) {
  if (importance === "required") {
    return "required";
  }

  const context = requirementContextFromJobContent({ evidence, jobContent });
  if (context === "required") {
    return "required";
  }
  if (context === "preferred" && importance === "signal") {
    return "preferred";
  }
  return importance;
}

function requirementContextFromJobContent({ evidence, jobContent }) {
  const normalizedEvidence = normalizeRequirementContext(evidence);
  if (!normalizedEvidence) {
    return "";
  }

  const lines = String(jobContent || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  let currentHeading = "";

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (isLikelyJobContentHeading(line)) {
      currentHeading = line;
    }

    if (!normalizeRequirementContext(line).includes(normalizedEvidence)) {
      continue;
    }

    const contextWindow = [
      currentHeading,
      ...lines.slice(Math.max(0, index - 3), Math.min(lines.length, index + 2)),
    ].join(" ");

    if (isPreferredRequirementContext(contextWindow)) {
      return "preferred";
    }
    if (isRequiredRequirementContext(contextWindow)) {
      return "required";
    }
  }

  return "";
}

function isLikelyJobContentHeading(line) {
  const normalized = normalizeRequirementContext(line);
  return normalized.length > 0
    && normalized.length <= 80
    && !/^[*\-•]\s/.test(String(line || ""))
    && (
      isRequiredRequirementContext(line)
      || isPreferredRequirementContext(line)
      || /\b(qualifications?|skills?|experience|about you|what you will do|what you'll do)\b/i.test(line)
    );
}

function isRequiredRequirementContext(value) {
  return /\b(required|requirements?|minimum qualifications?|qualifications?|responsibilities|what you will do|what you'll do|must have|you will)\b/i.test(value);
}

function isPreferredRequirementContext(value) {
  return /\b(preferred|nice to have|bonus|plus|desired|ideally|optional)\b/i.test(value);
}

function normalizeRequirementContext(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}+#.]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}
