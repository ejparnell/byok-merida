import { normalizeText, toPlainSingleLine } from "./text.js";
import { richText } from "./notionBlocks.js";
import { textSupportsEvidence } from "./evidenceSupport.js";

export const ANALYSIS_HEADING = "Job Posting Analysis";
export const JOB_CONTENT_HEADING = "Job Content";

const CONTROLLED_GROUPS = [
  "Databases",
  "APIs & Integrations",
  "Frameworks & Libraries",
  "Programming Languages",
  "Cloud & Platforms",
  "Testing & Quality",
  "Architecture & Systems",
  "DevOps & Tooling",
  "Workflow & Collaboration",
  "Domain Knowledge",
  "Other",
];

const GENERIC_SKILL_NAMES = new Set([
  "self-starter",
  "fast-paced",
  "excellent communicator",
  "communication",
  "team player",
  "detail-oriented",
  "detail oriented",
]);

export function hasAnalysisSection(blocks) {
  return blocks.some((block) => isHeading(block, "heading_2", ANALYSIS_HEADING));
}

export function extractJobContentFromBlocks(blocks) {
  const lines = [];
  let inJobContent = false;

  for (const block of blocks) {
    if (isHeading(block, "heading_2", JOB_CONTENT_HEADING)) {
      inJobContent = true;
      continue;
    }

    if (!inJobContent) {
      continue;
    }

    if (block.type === "heading_2") {
      break;
    }

    const text = blockPlainText(block);
    if (text) {
      lines.push(text);
    }
  }

  return normalizeText(lines.join("\n"));
}

export function buildAnalysisBlocks(analysis) {
  const summary = analysis.summary.join(" ");
  const blocks = [
    heading("heading_2", ANALYSIS_HEADING),
    heading("heading_3", "Summary"),
    paragraph(summary),
    heading("heading_3", "Skill Signals"),
  ];

  if (analysis.skillGroups.length === 0) {
    blocks.push(bullet("Other: No explicit Skill Signals found."));
    return blocks;
  }

  for (const group of analysis.skillGroups) {
    const names = group.signals.map((signal) => signal.name).filter(Boolean);
    if (names.length > 0) {
      blocks.push(bullet(`${group.label}: ${names.join(", ")}`));
    }
  }

  return blocks;
}

export function parseAndValidateAnalysisJson(content, jobContent) {
  const trimmed = String(content || "").trim();
  if (!trimmed) {
    throw new Error("DeepSeek returned empty analysis content.");
  }

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("DeepSeek analysis response was not valid JSON.");
  }

  return validateAnalysis(parsed, jobContent);
}

export function validateAnalysis(input, jobContent) {
  const summary = validateSummary(input?.summary);
  const skillGroups = validateSkillGroups(input?.skillGroups, jobContent);

  return {
    summary,
    skillGroups,
  };
}

export function normalizeGroupLabel(label) {
  const value = String(label || "").toLowerCase();

  if (/\b(database|sql|postgres|mongo|data store|warehouse)\b/.test(value)) return "Databases";
  if (/\b(apis?|rest|graphql|integration|webhook|fastapi|service)\b/.test(value)) return "APIs & Integrations";
  if (/\b(framework|library|react|next|express|django|fastapi)\b/.test(value)) return "Frameworks & Libraries";
  if (/\b(language|javascript|typescript|python|java|ruby|go|sql)\b/.test(value)) return "Programming Languages";
  if (/\b(cloud|aws|azure|gcp|platform|vercel|netlify)\b/.test(value)) return "Cloud & Platforms";
  if (/\b(test|quality|qa|jest|vitest|cypress|playwright)\b/.test(value)) return "Testing & Quality";
  if (/\b(architecture|system|distributed|scalability|design)\b/.test(value)) return "Architecture & Systems";
  if (/\b(devops|ci|cd|docker|kubernetes|deployment|terraform)\b/.test(value)) return "DevOps & Tooling";
  if (/\b(workflow|collaboration|agile|scrum|documentation|stakeholder|async)\b/.test(value)) return "Workflow & Collaboration";
  if (/\b(domain|healthcare|finance|education|compliance|clinical)\b/.test(value)) return "Domain Knowledge";

  return CONTROLLED_GROUPS.includes(label) ? label : "Other";
}

export function blockPlainText(block) {
  const typed = block?.[block.type];
  const richText = typed?.rich_text || [];
  return richText.map((part) => part.plain_text || part.text?.content || "").join("").trim();
}

function validateSummary(summary) {
  if (!Array.isArray(summary) || summary.length !== 3) {
    throw new Error("Analysis summary must contain exactly three sentences.");
  }

  return summary.map((sentence) => {
    const value = toPlainSingleLine(sentence, 800);
    if (!value) {
      throw new Error("Analysis summary sentences must be non-empty.");
    }
    return value;
  });
}

function validateSkillGroups(groups, jobContent) {
  if (!Array.isArray(groups)) {
    throw new Error("Analysis skillGroups must be an array.");
  }

  const grouped = new Map();

  for (const group of groups) {
    const label = normalizeGroupLabel(group?.label);
    const signals = Array.isArray(group?.signals) ? group.signals : [];

    for (const signal of signals) {
      const name = toPlainSingleLine(signal?.name, 120);
      const evidence = toPlainSingleLine(signal?.evidence, 300);

      if (!name || !evidence) {
        throw new Error("Each Skill Signal must include a name and evidence.");
      }

      if (GENERIC_SKILL_NAMES.has(name.toLowerCase())) {
        continue;
      }

      if (!textSupportsEvidence(jobContent, { evidence, alternateEvidence: name })) {
        throw new Error(`Skill Signal evidence was not found in Job Content: ${evidence}`);
      }

      if (!grouped.has(label)) {
        grouped.set(label, []);
      }

      grouped.get(label).push({ name, evidence });
    }
  }

  return [...grouped.entries()]
    .map(([label, signals]) => ({ label, signals: dedupeSignals(signals) }))
    .filter((group) => group.signals.length > 0);
}

function dedupeSignals(signals) {
  const seen = new Set();
  const output = [];

  for (const signal of signals) {
    const key = signal.name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    output.push(signal);
  }

  return output;
}

function isHeading(block, type, text) {
  return block?.type === type && blockPlainText(block).toLowerCase() === text.toLowerCase();
}

function heading(type, content) {
  return block(type, content);
}

function paragraph(content) {
  return block("paragraph", content);
}

function bullet(content) {
  return block("bulleted_list_item", content);
}

function block(type, content) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: richText(content),
    },
  };
}
